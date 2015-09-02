# -*- coding: utf-8 -*-
#    Copyright 2013 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from netaddr import IPNetwork
import six

from oslo_serialization import jsonutils

from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema.network_template import \
    NETWORK_TEMPLATE
from nailgun.api.v1.validators.json_schema import networks
from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import Node
from nailgun.errors import errors
from nailgun import objects


class NetworkConfigurationValidator(BasicValidator):
    @classmethod
    def base_validation(cls, data):
        valid_data = cls.validate_json(data)
        valid_data = cls.prepare_data(valid_data)

        return valid_data

    @classmethod
    def validate_networks_data(cls, data, cluster, networks_required=True):
        data = cls.base_validation(data)

        if networks_required or 'networks' in data:
            data = cls.validate_networks_update(data, cluster)

        cls.additional_network_validation(data, cluster)

        return data

    @classmethod
    def validate_network_group(cls, ng_data, ng_db, cluster):
        net_id = ng_data['id']
        cidr = ng_data.get('cidr', ng_db.cidr)
        ip_ranges = ng_data.get(
            'ip_ranges',
            [(r.first, r.last) for r in ng_db.ip_ranges])

        release = ng_data.get('release', ng_db.get('release'))
        if release != ng_db.get('release'):
            raise errors.InvalidData('Network release could not be changed.')

        # values are always taken either from request or from DB
        meta = ng_data.get('meta', {})
        notation = meta.get('notation', ng_db.meta.get('notation'))
        use_gateway = meta.get('use_gateway',
                               ng_db.meta.get('use_gateway', False))
        gateway = ng_data.get('gateway', ng_db.get('gateway'))

        if use_gateway and not gateway:
            raise errors.InvalidData(
                "Flag 'use_gateway' cannot be provided without gateway")

        # Depending on notation required parameters must be either in
        # the request or DB
        if not ip_ranges and notation == consts.NETWORK_NOTATION.ip_ranges:
            raise errors.InvalidData(
                "No IP ranges were specified for network "
                "{0}".format(net_id))

        if notation in (consts.NETWORK_NOTATION.cidr,
                        consts.NETWORK_NOTATION.ip_ranges):
            if not cidr and not ng_db.cidr:
                raise errors.InvalidData(
                    "No CIDR was specified for network "
                    "{0}".format(net_id))
        if cluster.is_locked and cls._check_for_ip_conflicts(
                ng_data, cluster, notation, use_gateway):

            raise errors.InvalidData(
                "New IP ranges for network '{0}' conflict "
                "with already allocated IPs.".format(ng_data['name'])
            )

        return ng_data

    @classmethod
    def validate_networks_update(cls, data, cluster):
        cls.validate_schema(data, networks.NETWORK_GROUPS)

        net_ids = [ng['id'] for ng in data['networks']]
        ng_db_by_id = dict(
            (ng.id, ng) for ng in db().query(NetworkGroup).filter(
                NetworkGroup.id.in_(net_ids)
            )
        )
        missing_ids = set(net_ids).difference(ng_db_by_id)
        if missing_ids:
            raise errors.InvalidData(
                u"Networks with ID's [{0}] are not present in the "
                "database".format(
                    ', '.join(map(str, sorted(missing_ids)))
                )
            )

        for network in data['networks']:
            cls.validate_network_group(
                network, ng_db_by_id[network['id']], cluster)

        return data

    @classmethod
    def _check_for_ip_conflicts(cls, network, cluster, notation, use_gateway):
        """This method checks if any of already allocated IPs will be \
        out of all ip-ranges after networks update.
        """
        # skip admin network
        manager = objects.Cluster.get_network_manager(cluster)
        if network['id'] == manager.get_admin_network_group_id():
            return False

        ng_db = db().query(NetworkGroup).get(network['id'])

        ips = manager.get_assigned_ips_by_network_id(network['id'])
        ranges = []
        if notation == consts.NETWORK_NOTATION.ip_ranges:
            ranges = network.get('ip_ranges',
                                 [(x.first, x.last) for x in ng_db.ip_ranges])
        if notation == consts.NETWORK_NOTATION.cidr:
            cidr = network.get('cidr', ng_db.cidr)
            ip_network = IPNetwork(cidr)
            first_index = 2 if use_gateway else 1
            ranges = [(ip_network[first_index], ip_network[-1])]
        return not manager.check_ips_belong_to_ranges(ips, ranges)

    @classmethod
    def prepare_data(cls, data):
        """Prepares input data.

        Filter input data based on the fact that
        updating parameters of the fuel admin network
        is forbidden for default node group.

        Admin network cannot be updated because of:
        - sharing itself between environments;
        - having no mechanism to change its parameters on deployed Master node.
        """
        if data.get("networks"):
            default_admin = db.query(
                NetworkGroup).filter_by(group_id=None).first()
            data["networks"] = [
                n for n in data["networks"]
                if n.get("id") != default_admin.id
            ]

        return data

    @classmethod
    def additional_network_validation(cls, data, cluster):
        pass


class NovaNetworkConfigurationValidator(NetworkConfigurationValidator):

    @classmethod
    def additional_network_validation(cls, data, cluster):
        if 'networking_parameters' in data:
            cls.validate_schema(
                data,
                networks.NOVA_NETWORK_CONFIGURATION)


class NeutronNetworkConfigurationValidator(NetworkConfigurationValidator):
    @classmethod
    def validate_neutron_params(cls, data, **kwargs):
        d = cls.validate_json(data)
        np = d.get('networking_parameters')

        cls._check_multiple_floating_ip_ranges(np)

        cluster_id = kwargs.get("cluster_id")
        if cluster_id:
            cls._check_segmentation_type_changing(cluster_id, np)

        return d

    @classmethod
    def _check_segmentation_type_changing(cls, cluster_id, data):
        cluster = db().query(Cluster).get(cluster_id)
        if cluster and cluster.network_config:
            for k in ("segmentation_type", "net_l23_provider"):
                if k in data and getattr(cluster.network_config, k) != data[k]:
                    raise errors.InvalidData(
                        "Change of '{0}' is prohibited".format(k),
                        log_message=True
                    )

    @classmethod
    def _check_multiple_floating_ip_ranges(cls, net_params):
        """Check that there is only one floating IP range
        in the input data.
        """
        # TODO(aroma): if only one IP range is supported
        # by the protocol we should get rid of the nested
        # list then
        if len(net_params.get('floating_ranges', [])) > 1:
            raise errors.InvalidData(
                "Setting of multiple floating IP ranges is prohibited")

    @classmethod
    def additional_network_validation(cls, data, cluster):
        if 'networking_parameters' in data:
            cls.validate_schema(
                data,
                networks.NEUTRON_NETWORK_CONFIGURATION)
            cls.validate_neutron_params(
                jsonutils.dumps(data),
                cluster_id=cluster.id
            )


class NetAssignmentValidator(BasicValidator):
    @classmethod
    def validate(cls, node):
        if not isinstance(node, dict):
            raise errors.InvalidData(
                "Each node should be dict",
                log_message=True
            )
        if 'id' not in node:
            raise errors.InvalidData(
                "Each node should have ID",
                log_message=True
            )
        if 'interfaces' not in node or \
                not isinstance(node['interfaces'], list):
            raise errors.InvalidData(
                "Node '{0}': there is no 'interfaces' list".format(
                    node['id']),
                log_message=True
            )

        net_ids = set()
        for iface in node['interfaces']:
            if not isinstance(iface, dict):
                raise errors.InvalidData(
                    "Node '{0}': each interface should be a dict "
                    "(got '{1}')".format(node['id'], iface),
                    log_message=True
                )
            if 'type' not in iface:
                raise errors.InvalidData(
                    "Node '{0}': each interface must have a type".format(
                        node['id']),
                    log_message=True
                )
            if iface['type'] not in consts.NETWORK_INTERFACE_TYPES:
                raise errors.InvalidData(
                    "Node '{0}': unknown interface type".format(node['id']),
                    log_message=True
                )
            if iface['type'] == consts.NETWORK_INTERFACE_TYPES.ether \
                    and 'id' not in iface:
                raise errors.InvalidData(
                    "Node '{0}': each HW interface must have ID".format(
                        node['id']),
                    log_message=True
                )
            if iface['type'] == consts.NETWORK_INTERFACE_TYPES.bond:
                if 'name' not in iface:
                    raise errors.InvalidData(
                        "Node '{0}': each bond interface must have "
                        "name".format(node['id']),
                        log_message=True
                    )
                if 'slaves' not in iface \
                        or not isinstance(iface['slaves'], list) \
                        or len(iface['slaves']) < 2:
                    raise errors.InvalidData(
                        "Node '{0}': each bond interface must have two or more"
                        " slaves".format(node['id']),
                        log_message=True
                    )
                for slave in iface['slaves']:
                    if 'name' not in slave:
                        raise errors.InvalidData(
                            "Node '{0}', interface '{1}': each bond slave "
                            "must have name".format(node['id'], iface['name']),
                            log_message=True
                        )
                if 'bond_properties' in iface:
                    for k in iface['bond_properties'].keys():
                        if k not in consts.BOND_PROPERTIES:
                            raise errors.InvalidData(
                                "Node '{0}', interface '{1}': unknown bond "
                                "property '{2}'".format(
                                    node['id'], iface['name'], k),
                                log_message=True
                            )
                bond_mode = cls.get_bond_mode(iface)
                if not bond_mode:
                    raise errors.InvalidData(
                        "Node '{0}': bond interface '{1}' doesn't have "
                        "mode".format(node['id'], iface['name']),
                        log_message=True
                    )
                if bond_mode not in consts.BOND_MODES:
                    raise errors.InvalidData(
                        "Node '{0}': bond interface '{1}' has unknown "
                        "mode '{2}'".format(
                            node['id'], iface['name'], bond_mode),
                        log_message=True
                    )
            if 'assigned_networks' not in iface or \
                    not isinstance(iface['assigned_networks'], list):
                raise errors.InvalidData(
                    "Node '{0}', interface '{1}':"
                    " there is no 'assigned_networks' list".format(
                        node['id'], iface.get('id') or iface.get('name')),
                    log_message=True
                )

            for net in iface['assigned_networks']:
                if not isinstance(net, dict):
                    raise errors.InvalidData(
                        "Node '{0}', interface '{1}':"
                        " each assigned network should be a dict".format(
                            node['id'], iface.get('id') or iface.get('name')),
                        log_message=True
                    )
                if 'id' not in net:
                    raise errors.InvalidData(
                        "Node '{0}', interface '{1}':"
                        " each assigned network should have ID".format(
                            node['id'], iface.get('id') or iface.get('name')),
                        log_message=True
                    )
                if net['id'] in net_ids:
                    raise errors.InvalidData(
                        "Node '{0}': there is a duplicated network '{1}' in"
                        " assigned networks (second occurrence is in "
                        "interface '{2}')".format(
                            node['id'], net['id'],
                            iface.get('id') or iface.get('name')),
                        log_message=True
                    )
                net_ids.add(net['id'])
        return node

    @classmethod
    def get_bond_mode(cls, iface):
        bond_mode = None
        if 'mode' in iface:
            bond_mode = iface['mode']
        if 'mode' in iface.get('bond_properties', {}):
            bond_mode = iface['bond_properties']['mode']
        return bond_mode

    @classmethod
    def validate_structure(cls, webdata):
        node_data = cls.validate_json(webdata)
        return cls.validate(node_data)

    @classmethod
    def validate_collection_structure_and_data(cls, webdata):
        data = cls.validate_json(webdata)
        if not isinstance(data, list):
            raise errors.InvalidData(
                "Data should be list of nodes",
                log_message=True
            )
        for node_data in data:
            cls.validate(node_data)
            cls.verify_data_correctness(node_data)
        return data

    @classmethod
    def validate_structure_and_data(cls, webdata, node_id):
        interfaces_data = cls.validate_json(webdata)
        node_data = {'id': node_id, 'interfaces': interfaces_data}
        cls.validate(node_data)
        cls.verify_data_correctness(node_data)
        return interfaces_data

    @classmethod
    def verify_data_correctness(cls, node):
        db_node = db().query(Node).filter_by(id=node['id']).first()
        if not db_node:
            raise errors.InvalidData(
                "There is no node with ID '{0}' in DB".format(node['id']),
                log_message=True
            )
        if objects.Node.hardware_info_locked(db_node):
            raise errors.InvalidData(
                "Node '{0}': Interfaces configuration can't be changed after "
                "or during deployment.".format(db_node.id))
        interfaces = node['interfaces']
        db_interfaces = db_node.nic_interfaces
        net_manager = objects.Cluster.get_network_manager(db_node.cluster)
        network_group_ids = net_manager.get_node_networkgroups_ids(db_node)

        bonded_eth_ids = set()
        pxe_iface_name = net_manager._get_pxe_iface_name(db_node)
        if not pxe_iface_name:
            raise errors.InvalidData(
                "Node '{0}': Interfaces configuration can't be changed if"
                "there is no pxe interface in DB".format(node['id']),
                log_message=True
            )

        for iface in interfaces:
            iface_nets = [n.get('name')
                          for n in iface.get('assigned_networks')]
            if iface['type'] == consts.NETWORK_INTERFACE_TYPES.ether:
                db_iface = next(six.moves.filter(
                    lambda i: i.id == iface['id'],
                    db_interfaces
                ), None)
                if not db_iface:
                    raise errors.InvalidData(
                        "Node '{0}': there is no interface with ID '{1}'"
                        " in DB".format(node['id'], iface['id']),
                        log_message=True
                    )
                if not db_iface.pxe:
                    if consts.NETWORKS.fuelweb_admin in iface_nets:
                        raise errors.InvalidData(
                            "Node '{0}': admin network can not be assigned to"
                            " non-pxe interface {1}".format(node['id'],
                                                            iface['name']),
                            log_message=True
                        )
            elif iface['type'] == consts.NETWORK_INTERFACE_TYPES.bond:
                pxe_iface_present = False
                for slave in iface['slaves']:
                    iface_id = [i.id for i in db_interfaces
                                if i.name == slave['name']]
                    if slave["name"] == pxe_iface_name:
                        pxe_iface_present = True
                    if iface_id:
                        if iface_id[0] in bonded_eth_ids:
                            raise errors.InvalidData(
                                "Node '{0}': interface '{1}' is used in bonds "
                                "more than once".format(
                                    node['id'], iface_id[0]),
                                log_message=True
                            )
                        bonded_eth_ids.add(iface_id[0])
                    else:
                        raise errors.InvalidData(
                            "Node '{0}': there is no interface '{1}' found "
                            "for bond '{2}' in DB".format(
                                node['id'], slave['name'], iface['name']),
                            log_message=True
                        )

                if consts.NETWORKS.fuelweb_admin in iface_nets:
                    prohibited_modes = net_manager.\
                        get_prohibited_admin_bond_modes()
                    bond_mode = cls.get_bond_mode(iface)
                    if bond_mode in prohibited_modes:
                        raise errors.InvalidData(
                            "Node '{0}': interface '{1}' belongs to "
                            "admin network and has lacp mode '{2}'".format(
                                node['id'], iface['name'], bond_mode),
                            log_message=True
                        )
                    if not pxe_iface_present:
                        raise errors.InvalidData(
                            "Node '{0}': interface '{1}' belongs to "
                            "admin network and doesn't contain node's pxe "
                            "interface '{2}'".format(
                                node['id'], iface['name'], pxe_iface_name),
                            log_message=True
                        )

            for net in iface['assigned_networks']:
                if net['id'] not in network_group_ids:
                    raise errors.InvalidData(
                        "Network '{0}' doesn't exist for node {1}".format(
                            net['id'], node['id']),
                        log_message=True
                    )
                network_group_ids.remove(net['id'])

        if network_group_ids:
            str_ng_ids = ["'" + str(ng_id) + "'"
                          for ng_id in network_group_ids]
            raise errors.InvalidData(
                "Node '{0}': {1} network(s) are left unassigned".format(
                    node['id'], ",".join(str_ng_ids)),
                log_message=True
            )

        for iface in interfaces:
            if iface['type'] == consts.NETWORK_INTERFACE_TYPES.ether \
                    and iface['id'] in bonded_eth_ids \
                    and len(iface['assigned_networks']) > 0:
                raise errors.InvalidData(
                    "Node '{0}': interface '{1}' cannot have "
                    "assigned networks as it is used in "
                    "bond".format(node['id'], iface['id']),
                    log_message=True
                )


class NetworkGroupValidator(NetworkConfigurationValidator):

    @classmethod
    def validate(cls, data):
        d = cls.validate_json(data)
        node_group = objects.NodeGroup.get_by_uid(d.get('group_id'))

        if not node_group:
            raise errors.InvalidData(
                "Node group with ID {0} does not exist".format(
                    d.get('group_id'))
            )

        if objects.NetworkGroup.get_from_node_group_by_name(
                node_group.id, d.get('name')):
            raise errors.AlreadyExists(
                "Network with name {0} already exists "
                "in node group {1}".format(d['name'], node_group.name)
            )

        return d

    @classmethod
    def validate_update(cls, data, **kwargs):
        valid_data = cls.validate(data)
        ng_db = db().query(NetworkGroup).get(valid_data['id'])
        if not ng_db.group_id:
            # Only default Admin-pxe network doesn't have group_id.
            # It cannot be changed.
            raise errors.InvalidData(
                "Default Admin-pxe network cannot be changed")
        return cls.validate_network_group(
            valid_data, ng_db, ng_db.nodegroup.cluster)

    @classmethod
    def validate_delete(cls, data, instance, force=False):
        if not instance.group_id:
            # Only default Admin-pxe network doesn't have group_id.
            # It cannot be deleted.
            raise errors.InvalidData(
                "Default Admin-pxe network cannot be deleted")
        elif instance.nodegroup.cluster.is_locked:
            raise errors.InvalidData(
                "Networks cannot be deleted after deployment")


class NetworkTemplateValidator(BasicValidator):

    @classmethod
    def validate(cls, data, instance=None):
        parsed = super(NetworkTemplateValidator, cls).validate(data)
        cls.validate_schema(parsed, NETWORK_TEMPLATE)

        # Ensure templates requested in templates_for_node_role are
        # present in network_scheme
        if not parsed['adv_net_template']:
            raise errors.InvalidData("No node groups are defined")
        for ng_name, node_group in six.iteritems(parsed['adv_net_template']):
            defined_templates = set(six.iterkeys(node_group['network_scheme']))
            not_found = set()
            for templates_by_role in six.itervalues(
                    node_group['templates_for_node_role']):
                for template in templates_by_role:
                    if template not in defined_templates:
                        not_found.add(template)
            if not_found:
                raise errors.InvalidData(
                    "Requested templates {0} were not found for node "
                    "group {1}".format(', '.join(not_found), ng_name))
            if not defined_templates:
                raise errors.InvalidData(
                    "No templates are defined for node group {0}".format(
                        ng_name))

        return parsed
