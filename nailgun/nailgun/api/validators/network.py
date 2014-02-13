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

from netaddr import AddrFormatError
from netaddr import IPNetwork

from nailgun.api.validators.base import BasicValidator
from nailgun.consts import NETWORK_INTERFACE_TYPES
from nailgun.consts import OVS_BOND_MODES
from nailgun.db import db
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import Node
from nailgun.errors import errors


class NetworkConfigurationValidator(BasicValidator):

    @classmethod
    def validate_networks_update(cls, data):
        d = cls.validate_json(data)
        if not d:
            raise errors.InvalidData(
                "No valid data received",
                log_message=True
            )

        networks = d.get('networks')
        if not isinstance(networks, list):
            raise errors.InvalidData(
                "'networks' is expected to be an array",
                log_message=True
            )
        for i in networks:
            if 'id' not in i:
                raise errors.InvalidData(
                    "No 'id' param presents for '{0}' network".format(i),
                    log_message=True
                )

            if i.get('name') == 'public':
                try:
                    IPNetwork('0.0.0.0/' + i['netmask'])
                except (AddrFormatError, KeyError):
                    raise errors.InvalidData(
                        "Invalid netmask for public network",
                        log_message=True
                    )
        return d


class NovaNetworkConfigurationValidator(NetworkConfigurationValidator):

    @classmethod
    def validate_dns_servers_update(cls, data):
        d = cls.validate_json(data)

        dns_servers = d['dns_nameservers'].get("nameservers", [])

        if not isinstance(dns_servers, list):
            raise errors.InvalidData(
                "It's expected to receive array of DNS servers, "
                "not a single object",
                log_message=True
            )
        if len(dns_servers) < 2:
            raise errors.InvalidData(
                "There should be at least two DNS servers",
                log_message=True
            )

        return d


class NeutronNetworkConfigurationValidator(NetworkConfigurationValidator):

    @classmethod
    def validate_neutron_params(cls, data, **kwargs):
        d = cls.validate_json(data)
        np = d.get('neutron_parameters')
        cluster_id = kwargs.get("cluster_id")
        if cluster_id:
            cluster = db().query(Cluster).get(cluster_id)
            if cluster and cluster.neutron_config:
                cfg = cluster.neutron_config
                for k in ("segmentation_type",):
                    if k in np and getattr(cfg, k) != np[k]:
                        raise errors.InvalidData(
                            "Change of '{0}' is prohibited".format(k),
                            log_message=True
                        )
        return d


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
                "There is no 'interfaces' list for node '{0}'".format(
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
            if iface['type'] not in NETWORK_INTERFACE_TYPES:
                raise errors.InvalidData(
                    "Node '{0}': unknown interface type".format(node['id']),
                    log_message=True
                )
            if iface['type'] != NETWORK_INTERFACE_TYPES.bond \
                    and 'id' not in iface:
                raise errors.InvalidData(
                    "Node '{0}': each HW interface must have ID".format(
                        node['id']),
                    log_message=True
                )
            if iface['type'] == NETWORK_INTERFACE_TYPES.bond:
                if 'id' not in iface and 'name' not in iface:
                    raise errors.InvalidData(
                        "Node '{0}': each bond interface must have "
                        "either ID or name".format(node['id']),
                        log_message=True
                    )
                if 'mode' not in iface:
                    raise errors.InvalidData(
                        "Node '{0}': each bond interface must have "
                        "mode".format(node['id']),
                        log_message=True
                    )
                if iface['mode'] not in OVS_BOND_MODES:
                    raise errors.InvalidData(
                        "Node '{0}': bond interface has unknown "
                        "mode '{1}'".format(node['id'], iface['mode']),
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
                    if 'id' not in iface and 'name' not in iface:
                        raise errors.InvalidData(
                            "Node '{0}': each bond interface must have "
                            "either ID or Name".format(node['id']),
                            log_message=True
                        )
            if 'assigned_networks' not in iface or \
                    not isinstance(iface['assigned_networks'], list):
                raise errors.InvalidData(
                    "There is no 'assigned_networks' list"
                    " in interface '{0}' in node '{1}'".format(
                        iface['id'], node['id']),
                    log_message=True
                )

            for net in iface['assigned_networks']:
                if not isinstance(net, dict):
                    raise errors.InvalidData(
                        "Node '{0}', interface '{1}':"
                        " each assigned network should be a dict".format(
                            iface['id'], node['id']),
                        log_message=True
                    )
                if 'id' not in net:
                    raise errors.InvalidData(
                        "Node '{0}', interface '{1}':"
                        " each assigned network should have ID".format(
                            iface['id'], node['id']),
                        log_message=True
                    )
                if net['id'] in net_ids:
                    raise errors.InvalidData(
                        "Assigned networks for node '{0}' have"
                        " a duplicate network '{1}' (second"
                        " occurrence in interface '{2}')".format(
                            node['id'], net['id'], iface['id']),
                        log_message=True
                    )
                net_ids.add(net['id'])
        return node

    @classmethod
    def validate_structure(cls, webdata):
        node_data = cls.validate_json(webdata)
        return cls.validate(node_data)

    @classmethod
    def validate_collection_structure(cls, webdata):
        data = cls.validate_json(webdata)
        if not isinstance(data, list):
            raise errors.InvalidData(
                "Data should be list of nodes",
                log_message=True
            )
        for node_data in data:
            cls.validate(node_data)
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
        interfaces = node['interfaces']
        db_interfaces = db_node.nic_interfaces
        network_group_ids = []
        for nic in db_node.interfaces:
            for ng in nic.assigned_networks_list:
                network_group_ids.append(ng.id)

        if not network_group_ids:
            raise errors.InvalidData(
                "There are no networks for node '{0}' in DB".format(
                    node['id']),
                log_message=True
            )

        bonded_eth_ids = set()
        for iface in interfaces:
            if iface['type'] == NETWORK_INTERFACE_TYPES.ether:
                db_iface = filter(
                    lambda i: i.id == iface['id'],
                    db_interfaces
                )
                if not db_iface:
                    raise errors.InvalidData(
                        "There is no interface with ID '{0}'"
                        " at node '{1}' in DB".format(iface['id'], node['id']),
                        log_message=True
                    )
            elif iface['type'] == NETWORK_INTERFACE_TYPES.bond:
                for slave in iface['slaves']:
                    if slave.get('id'):
                        iface_id = [i.id for i in db_interfaces
                                    if i.id == slave['id']]
                    if slave.get('name'):
                        iface_id = [i.id for i in db_interfaces
                                    if i.name == slave['name']]
                    if iface_id:
                        if iface_id[0] in bonded_eth_ids:
                            raise errors.InvalidData(
                                "More than one bond use interface '{0}'"
                                " at node '{1}'".format(iface[0], node['id']),
                                log_message=True
                            )
                        bonded_eth_ids.add(iface_id[0])
                    else:
                        raise errors.InvalidData(
                            "There is no interface found for bond '{0}'"
                            " at node '{1}' in DB".format(iface, node['id']),
                            log_message=True
                        )

            for net in iface['assigned_networks']:
                if net['id'] not in network_group_ids:
                    raise errors.InvalidData(
                        "Node '{0}' must not be connected to network "
                        "with ID '{1}'".format(node['id'], net['id']),
                        log_message=True
                    )
                network_group_ids.remove(net['id'])

        # Check if there are unassigned networks for this node.
        if network_group_ids:
            raise errors.InvalidData(
                "Some networks are left unassigned for node '{0}'".format(
                    node['id']),
                log_message=True
            )

        for iface in interfaces:
            if iface['type'] == NETWORK_INTERFACE_TYPES.ether \
                    and iface['id'] in bonded_eth_ids \
                    and len(iface['assigned_networks']) > 0:
                raise errors.InvalidData(
                    "Interface '{0}' at node '{1}' cannot have "
                    "assigned networks as it's used in "
                    "bond".format(iface['id'], node['id']),
                    log_message=True
                )
