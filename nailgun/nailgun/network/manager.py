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

from collections import defaultdict
from itertools import islice
import operator

from netaddr import IPAddress
from netaddr import IPNetwork
from netaddr import IPRange
import six
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import not_

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import IPAddr
from nailgun.db.sqlalchemy.models import NetworkBondAssignment
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import NetworkNICAssignment
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import NodeBondInterface
from nailgun.db.sqlalchemy.models import NodeGroup
from nailgun.db.sqlalchemy.models import NodeNICInterface
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.network import utils
from nailgun import objects
from nailgun.objects.serializers.node import NodeInterfacesSerializer
from nailgun.settings import settings
from nailgun.utils.zabbix import ZabbixManager


class NetworkManager(object):

    @classmethod
    def get_admin_network_group_id(cls, node_id=None):
        """Method for receiving Admin NetworkGroup ID.

        :param node_id: Node id
        :type  node_id: int
        :returns: Admin NetworkGroup ID or None.
        :raises: errors.AdminNetworkNotFound
        """
        return cls.get_admin_network_group(node_id=node_id).id

    @classmethod
    def get_admin_network_group(cls, node_id=None):
        """Method for receiving Admin NetworkGroup.

        :param node_id: Node id
        :type  node_id: int
        :returns: Admin NetworkGroup or None.
        :raises: errors.AdminNetworkNotFound
        """
        admin_ng = None
        admin_ngs = db().query(NetworkGroup).filter_by(
            name=consts.NETWORKS.fuelweb_admin,
        )
        if node_id:
            node_db = db().query(Node).get(node_id)
            admin_ng = admin_ngs.filter_by(group_id=node_db.group_id).first()

        admin_ng = admin_ng or admin_ngs.filter_by(group_id=None).first()

        if not admin_ng:
            raise errors.AdminNetworkNotFound()
        return admin_ng

    @classmethod
    def reusable_ip_address(cls, node, network):
        """Verifies that ip belongs to network and creates IPAddr in case it is

        :param node: Node database object.
        :param network: Network database object.
        :returns: IPAddr object or None
        """
        if node.ip and cls.check_ip_belongs_to_net(node.ip, network):
            return IPAddr(node=node.id,
                          ip_addr=node.ip,
                          network=network.id)
        return None

    @classmethod
    def assign_admin_ips(cls, nodes):
        """Method for assigning admin IP addresses to nodes.

        :param nodes: Nodes DB objects
        :type  nodes: list
        :returns: None
        """
        # Check which nodes need ips
        # verification that node.ip (which is reported by agent) belongs
        # to one of the ranges of required to be able to reuse admin ip address
        # also such approach is backward compatible
        nodes_need_ips = defaultdict(list)

        # Creating index for admin network groups by nodegroup id
        admin_nw_groups_idx = IndexedData.get_network_groups_index(
            names=(consts.NETWORKS.fuelweb_admin,))

        # Creating index for ips by node id and network id
        ips_node_network_idx = IndexedData.get_ips_node_nw_group_index(
            db().query(IPAddr))

        for node in nodes:
            admin_net = IndexedData.get_admin_nw_group(
                admin_nw_groups_idx, node)
            ips_key = IndexedData.ips_node_nw_group_key(node, admin_net)
            node_admin_ips = ips_node_network_idx[ips_key]
            logger.debug(u"Trying to assign admin ip: node=%s", node.id)
            if not node_admin_ips:
                reusable_ip = cls.reusable_ip_address(node, admin_net)
                if reusable_ip:
                    db().add(reusable_ip)
                else:
                    nodes_need_ips[admin_net].append(node.id)
        db().flush()

        for admin_net, nodes in six.iteritems(nodes_need_ips):
            free_ips = cls.get_free_ips(admin_net, len(nodes))
            for ip, n in zip(free_ips, nodes):
                ip_db = IPAddr(node=n,
                               ip_addr=ip,
                               network=admin_net.id)
                db().add(ip_db)
            db().flush()

    @classmethod
    def get_node_networks_ips(cls, node):
        return dict(db().query(NetworkGroup.name, IPAddr.ip_addr).
                    filter(NetworkGroup.group_id == node.group_id).
                    filter(IPAddr.network == NetworkGroup.id).
                    filter(IPAddr.node == node.id))

    @classmethod
    def set_node_networks_ips(cls, node, ips_by_network_name):
        ngs = db().query(NetworkGroup.name, IPAddr).\
            filter(NetworkGroup.group_id == node.group_id).\
            filter(IPAddr.network == NetworkGroup.id).\
            filter(IPAddr.node == node.id).\
            filter(NetworkGroup.name.in_(ips_by_network_name))
        for ng_name, ip_addr in ngs:
            ip_addr.ip_addr = ips_by_network_name[ng_name]
        db().flush()

    @classmethod
    def set_node_netgroups_ids(cls, node, netgroups_id_mapping):
        ip_addrs = db().query(IPAddr).filter(IPAddr.node == node.id)
        for ip_addr in ip_addrs:
            ip_addr.network = netgroups_id_mapping[ip_addr.network]
        db().flush()

    @classmethod
    def set_nic_assignment_netgroups_ids(cls, node, netgroups_id_mapping):
        nic_assignments = db.query(NetworkNICAssignment).\
            join(NodeNICInterface).\
            filter(NodeNICInterface.node_id == node.id)
        for nic_assignment in nic_assignments:
            nic_assignment.network_id = \
                netgroups_id_mapping[nic_assignment.network_id]
        db().flush()

    @classmethod
    def set_bond_assignment_netgroups_ids(cls, node, netgroups_id_mapping):
        bond_assignments = db.query(NetworkBondAssignment).\
            join(NodeBondInterface).\
            filter(NodeBondInterface.node_id == node.id)
        for bond_assignment in bond_assignments:
            bond_assignment.network_id = \
                netgroups_id_mapping[bond_assignment.network_id]
        db().flush()

    @classmethod
    def assign_ips(cls, nodes, network_name):
        """Idempotent assignment IP addresses to nodes.

        All nodes passed as first argument get IP address
        from network, referred by network_name.
        If node already has IP address from this network,
        it remains unchanged. If one of the nodes is the
        node from other cluster, this func will fail.

        :param nodes: List of nodes DB objects
        :type  nodes: list
        :param network_name: Network name
        :type  network_name: str
        :returns: None
        :raises: Exception, errors.AssignIPError
        """
        cluster_id = nodes[0].cluster_id
        for node in nodes:
            if node.cluster_id != cluster_id:
                raise Exception(
                    u"Node id='{0}' doesn't belong to cluster_id='{1}'".format(
                        node.id,
                        cluster_id
                    )
                )

        network_groups = db().query(NetworkGroup).\
            filter_by(name=network_name)

        if not network_groups:
            raise errors.AssignIPError(
                u"Network '%s' for cluster_id=%s not found." %
                (network_name, cluster_id)
            )

        cluster = objects.Cluster.get_by_uid(cluster_id)
        default_group_id = objects.Cluster.get_default_group(cluster).id

        # Check which nodes need ips
        nodes_need_ips = defaultdict(list)

        # Creating index for network groups by nodegroup id
        nw_group_nodegroup_id_idx = IndexedData.build_index(
            network_groups, operator.attrgetter('group_id'))

        # Creating index for non admin ips by node id and network id
        non_admin_ips_node_network_idx = IndexedData.\
            get_ips_node_nw_group_index(cls._get_ips_except_admin())

        def get_index_in_network_group_id_idx(node_db):
            """Returns key in networks index for given Node DB object

            If node doesn't belongs to any nodegroup default nodegroup
            will be selected

            :param node_db: Node DB object
            :return: key for networks index
            """
            g_id = node_db.group_id or default_group_id
            nw = (nw_group_nodegroup_id_idx.get(g_id) or
                  nw_group_nodegroup_id_idx.get(None))
            return '{0}_{1}'.format(node_db.id, nw.id)

        for node in nodes:
            node_id = node.id

            if network_name == 'public' and \
                    not objects.Node.should_have_public_with_ip(node):
                continue

            group_id = node.group_id or default_group_id
            network = (nw_group_nodegroup_id_idx.get(group_id) or
                       nw_group_nodegroup_id_idx.get(None))

            idx_key = get_index_in_network_group_id_idx(node)
            node_ips = non_admin_ips_node_network_idx[idx_key]

            # check if any of node_ips in required ranges
            ip_already_assigned = False

            for ip in node_ips:
                if cls.check_ip_belongs_to_net(ip.ip_addr, network):
                    logger.info(
                        u"Node id='{0}' already has an IP address "
                        "inside '{1}' network.".format(
                            node_id,
                            network.name
                        )
                    )
                    ip_already_assigned = True
                    break

            if ip_already_assigned:
                continue

            nodes_need_ips[network].append(node_id)

        # Get and assign ips for nodes
        for network, nodes in six.iteritems(nodes_need_ips):
            free_ips = cls.get_free_ips(network, len(nodes))
            ip_addrs = []
            for ip, n_id in zip(free_ips, nodes):
                logger.info(
                    "Assigning IP for node '{0}' in network '{1}'".format(
                        n_id,
                        network_name
                    )
                )
                ip_addrs.append({'node': n_id, 'ip_addr': ip,
                                 'network': network.id})
            # TODO(akislitsky): use bulk_insert_mappings after
            # SQLAlchemy >= 1.0.0 will be used
            db().execute(IPAddr.__table__.insert(), ip_addrs)
            db().flush()

    @classmethod
    def assign_vip(cls, nodegroup, network_name,
                   vip_type=consts.NETWORK_VIP_TYPES.haproxy):
        """Idempotent assignment of VirtualIP addresses to nodegroup.

        Returns VIP for given nodegroup and network.
        It's required for HA deployment to have IP address
        not assigned to any of nodes. Currently we need one
        VIP per network in cluster. If cluster already has
        IP address from this network, it remains unchanged.
        If one of the nodes is the node from other cluster,
        this func will fail.

        :param nodegroup: Nodegroup instance
        :type nodegroup: NodeGroup model
        :param network_name: Network name
        :type  network_name: str
        :param vip_type: Type of VIP
        :type  vip_type: str
        :returns: assigned VIP (string)
        :raises: Exception
        """
        network = db().query(NetworkGroup).\
            filter_by(name=network_name, group_id=nodegroup.id).first()
        ips_in_use = None

        # FIXME:
        #   Built-in fuelweb_admin network doesn't belong to any node
        #   group, since it's shared between all clusters. So we need
        #   to handle this very special case if we want to be able
        #   to allocate VIP in default admin network.
        if not network and network_name == consts.NETWORKS.fuelweb_admin:
            network = cls.get_admin_network_group()

        if not network:
            raise errors.CanNotFindNetworkForNodeGroup(
                u"Network '{0}' for nodegroup='{1}' not found.".format(
                    network_name, nodegroup.name))

        cluster_vip = db().query(IPAddr).filter_by(
            network=network.id,
            node=None,
            vip_type=vip_type
        ).first()
        # check if cluster_vip is in required cidr: network.cidr
        if cluster_vip and cls.check_ip_belongs_to_net(cluster_vip.ip_addr,
                                                       network):
            return cluster_vip.ip_addr

        if network_name == consts.NETWORKS.fuelweb_admin:
            # Nodes not currently assigned to a cluster will still
            # have an IP from the appropriate admin network assigned.
            # So we much account for ALL admin IPs, not just the ones
            # allocated in the current cluster.
            node_ips = db().query(Node.ip).all()
            ips_in_use = set(ip[0] for ip in node_ips)

        # IP address has not been assigned, let's do it
        vip = cls.get_free_ips(network, ips_in_use=ips_in_use)[0]
        ne_db = IPAddr(network=network.id, ip_addr=vip, vip_type=vip_type)
        db().add(ne_db)
        db().flush()

        return vip

    @classmethod
    def assign_vips_for_net_groups(cls, cluster):
        """Calls cls.assign_vip for all of cluster's network_groups.

        :param cluster: Cluster instance
        :type  cluster: Cluster model
        :return: dict with vip definitions
        """
        result = {}

        nodegroup = objects.Cluster.get_controllers_node_group(cluster)
        for ng in cluster.network_groups:
            for vip_type in ng.meta.get('vips', ()):
                # used for backwards compatibility
                if vip_type == consts.NETWORK_VIP_TYPES.haproxy:
                    key = '{0}_vip'.format(ng.name)
                else:
                    key = '{0}_{1}_vip'.format(ng.name, vip_type)

                result[key] = cls.assign_vip(nodegroup, ng.name, vip_type)

        return result

    @classmethod
    def _get_assigned_vips_for_net_groups(cls, cluster):
        node_group_id = objects.Cluster.get_controllers_group_id(cluster)
        cluster_vips = db.query(IPAddr).join(IPAddr.network_data).filter(
            IPAddr.node.is_(None) &
            IPAddr.vip_type.isnot(None) &
            (NetworkGroup.group_id == node_group_id)
        )
        return cluster_vips

    @classmethod
    def get_assigned_vips(cls, cluster):
        """Return assigned VIPs mapped to names of network groups.

        :param cluster: Is an instance of :class:`objects.Cluster`.
        :returns: A dict of VIPs mapped to names of network groups and
                  they are grouped by the type.
        """
        cluster_vips = cls._get_assigned_vips_for_net_groups(cluster)
        vips = defaultdict(dict)
        for vip in cluster_vips:
            vips[vip.network_data.name][vip.vip_type] = vip.ip_addr
        return vips

    @classmethod
    def assign_given_vips_for_net_groups(cls, cluster, vips):
        """Assign given VIP addresses for network groups.

        This method is the opposite of the :func:`get_assigned_vips_ips`
        and compatible with results it returns. The method primarily
        used for the upgrading procedure of clusters to copy VIPs from
        one cluster to the other.

        :param cluster: Is an instance of :class:`objects.Cluster`.
        :param vips: A dict of VIPs mapped to names of network groups
                     that are grouped by the type.
        :raises: errors.AssignIPError
        """
        cluster_vips = cls._get_assigned_vips_for_net_groups(cluster)
        assigned_vips = defaultdict(dict)
        for vip in cluster_vips:
            assigned_vips[vip.network_data.name][vip.vip_type] = vip
        for net_group in cluster.network_groups:
            if net_group.name not in vips:
                continue
            assigned_vips_by_type = assigned_vips.get(net_group.name, {})
            for vip_type, ip_addr in six.iteritems(vips[net_group.name]):
                if not cls.check_ip_belongs_to_net(ip_addr, net_group):
                    ranges = [(rng.first, rng.last)
                              for rng in net_group.ip_ranges]
                    raise errors.AssignIPError(
                        "Cannot assign VIP with the address \"{0}\" because "
                        "it does not belong to the network {1} - \"{2}\" with "
                        "ranges {3} of the cluster \"{4}\"."
                        .format(ip_addr, net_group.id, net_group.name, ranges,
                                cluster.id))
                if vip_type in assigned_vips_by_type:
                    assigned_vip = assigned_vips_by_type[vip_type]
                    assigned_vip.ip_addr = ip_addr
                else:
                    vip = IPAddr(
                        network=net_group.id,
                        ip_addr=ip_addr,
                        vip_type=vip_type,
                    )
                    db().add(vip)
        db().flush()

    @classmethod
    def assign_vips_for_net_groups_for_api(cls, cluster):
        return cls.assign_vips_for_net_groups(cluster)

    @classmethod
    def check_ip_belongs_to_net(cls, ip_addr, network):
        addr = IPAddress(ip_addr)
        for r in network.ip_ranges:
            if addr in IPRange(r.first, r.last):
                return True
        return False

    @classmethod
    def check_ips_belong_to_ranges(cls, ips, ranges):
        """Checks ips belong to ranges

        Returns *True* if every of provided IPs belongs to any of
        provided ranges.

        :param ips: list of IPs (e.g. ['192.168.1.1', '127.0.0.1'], ...)
        :param ranges: list of IP ranges (e.g. [(first_ip, last_ip), ...])
        :return: *True* if all IPs belong to ranges or *False* otherwise
        """
        ranges = [IPRange(x[0], x[1]) for x in ranges]
        for ip in ips:
            ip_addr = IPAddress(ip)
            if not filter(lambda r: ip_addr in r, ranges):
                return False
        return True

    @classmethod
    def _iter_free_ips(cls, ip_ranges, ips_in_use):
        """Iterator over free IP addresses in given IP ranges.

        IP addresses which exist in ips_in_use are excluded from output.
        """
        for ip_range in ip_ranges:
            for ip_addr in ip_range:
                ip_str = str(ip_addr)
                if ip_str not in ips_in_use:
                    yield ip_str

    @classmethod
    def get_free_ips_from_ranges(cls, net_name, ip_ranges, ips_in_use, count):
        """Returns list of free IP addresses for given IP ranges.

        Required quantity of IPs is set in "count". IP addresses which exist
        in ips_in_use or exist in DB are excluded.
        """
        result = []
        ip_iterator = cls._iter_free_ips(ip_ranges, ips_in_use)
        while count > 0:
            # Eager IP mining to not run DB query on every single IP when just
            # 1 or 2 IPs are required and a long series of IPs from this range
            # are occupied already.
            free_ips = list(islice(ip_iterator,
                                   max(count, consts.MIN_IPS_PER_DB_QUERY)))
            if not free_ips:
                ranges_str = ','.join(str(r) for r in ip_ranges)
                raise errors.OutOfIPs(
                    "Not enough free IP addresses in ranges [{0}] of '{1}' "
                    "network".format(ranges_str, net_name))

            ips_in_db = db().query(
                IPAddr.ip_addr.distinct()
            ).filter(
                IPAddr.ip_addr.in_(free_ips)
            )

            for ip in ips_in_db:
                free_ips.remove(ip[0])

            result.extend(free_ips[:count])
            count -= len(free_ips[:count])

        return result

    @classmethod
    def get_free_ips(cls, network_group, num=1, ips_in_use=None):
        """Returns list of free IP addresses for given Network Group"""
        ips_in_use = ips_in_use or set()
        ip_ranges = [IPRange(r.first, r.last)
                     for r in network_group.ip_ranges]
        return cls.get_free_ips_from_ranges(
            network_group.name, ip_ranges, ips_in_use, num)

    @classmethod
    def _get_ips_except_admin(cls, node_id=None,
                              network_id=None, joined=False):
        """Returns IP addresses for node or network wo Admin Network IPs

        :param node_id: Node database ID.
        :type  node_id: int
        :param network_id: Network database ID.
        :type  network_id: int
        :returns: List of free IP addresses as SQLAlchemy objects.
        """
        ips = db().query(IPAddr).order_by(IPAddr.id)
        if joined:
            ips = ips.options(joinedload('network_data'))
        if node_id:
            ips = ips.filter_by(node=node_id)
        if network_id:
            ips = ips.filter_by(network=network_id)

        try:
            admin_net_id = cls.get_admin_network_group_id(node_id=node_id)
        except errors.AdminNetworkNotFound:
            admin_net_id = None
        if admin_net_id:
            ips = ips.filter(
                not_(IPAddr.network == admin_net_id)
            )

        return ips.all()

    @classmethod
    def _get_pxe_iface_name(cls, node):
        """Returns appropriate pxe iface's name

        In case when node has network scheme configured
        we can not rely on its pxe interface calculation
        algorithm anymore, because admin ip is moving to
        bridge and 'pxe' property will have 'False' value
        for all interfaces. In this case we should rely on
        db where actual pxe interface was saved during the
        bootstrap stage.
        In case when node for some reason has no pxe interface
        in db we should get pxe interface using appropriate
        function `get_admin_physical_iface`.
        """
        nic_pxe = next((i for i in node.meta['interfaces']
                        if i.get('pxe')),
                       None)
        nic_mac = next((i for i in node.meta['interfaces']
                        if i.get('mac').lower() == node.mac.lower()),
                       None)
        nic_ip = next((i for i in node.meta['interfaces']
                       if cls.is_ip_belongs_to_admin_subnet(i.get('ip'),
                                                            node.id)),
                      None)
        # 'pxe' flag is absent in agent's data often
        if nic_pxe and not (nic_pxe == nic_mac == nic_ip) or \
                nic_mac != nic_ip or (nic_ip and nic_ip['ip'] != node.ip):
            logger.warning(
                'PXE interface info is not consistent for node "%s"',
                node.full_name)
        # PXE sings are prioritised
        if nic_pxe:
            return nic_pxe['name']
        if nic_mac:
            return nic_mac['name']
        if nic_ip:
            return nic_ip['name']
        # shouldn't be raised as it's checked in check_interfaces_correctness()
        raise errors.CanNotFindInterface(
            'Cannot find PXE interface for node: {0}'.format(node.full_name))

    @classmethod
    def clear_assigned_ips(cls, node):
        db().query(IPAddr).filter_by(node=node.id).delete()

    @classmethod
    def clear_assigned_networks(cls, node):
        for nic in node.interfaces:
            while nic.assigned_networks_list:
                nic.assigned_networks_list.pop()
        db().flush()

    @classmethod
    def clear_bond_configuration(cls, node):
        for bond in node.bond_interfaces:
            db().delete(bond)

    @classmethod
    def get_default_interface_properties(cls):
        return {
            'mtu': None,
            'disable_offloading': False
        }

    @classmethod
    def get_default_interfaces_configuration(cls, node):
        """Returns default Networks-to-NICs assignment for given node

        Based on networks' configuration and metadata, default NICs'
        interface_properties, with no bonds configured.
        """
        nics = []
        group_id = (node.group_id or
                    objects.Cluster.get_default_group(node.cluster).id)
        node_group = db().query(NodeGroup).get(group_id)

        ngs = node_group.networks + [cls.get_admin_network_group(node.id)]
        ngs_by_id = dict((ng.id, ng) for ng in ngs)
        # sort Network Groups ids by map_priority
        to_assign_ids = list(
            zip(*sorted(
                [[ng.id, ng.meta['map_priority']]
                 for ng in ngs],
                key=lambda x: x[1]))[0]
        )
        ng_ids = set(ng.id for ng in ngs)
        ng_wo_admin_ids = \
            ng_ids ^ set([cls.get_admin_network_group_id(node.id)])
        pxe_iface = next(six.moves.filter(
            lambda i: i.pxe is True,
            node.nic_interfaces
        ), None)
        for nic in node.nic_interfaces:
            nic_dict = NodeInterfacesSerializer.serialize(nic)
            if 'interface_properties' in nic_dict:
                nic_dict['interface_properties'] = \
                    cls.get_default_interface_properties()
            nic_dict['assigned_networks'] = []

            if to_assign_ids:
                allowed_ids = \
                    ng_wo_admin_ids if nic != pxe_iface \
                    else ng_ids
                can_assign = [ng_id for ng_id in to_assign_ids
                              if ng_id in allowed_ids]
                assigned_ids = set()
                untagged_cnt = 0
                for ng_id in can_assign:
                    ng = ngs_by_id[ng_id]
                    dedicated = ng.meta.get('dedicated_nic')
                    untagged = (ng.vlan_start is None) \
                        and not ng.meta.get('neutron_vlan_range') \
                        and not ng.meta.get('ext_net_data')
                    if dedicated:
                        if not assigned_ids:
                            assigned_ids.add(ng_id)
                            break
                    elif untagged:
                        if untagged_cnt == 0:
                            assigned_ids.add(ng_id)
                            untagged_cnt += 1
                    else:
                        assigned_ids.add(ng_id)

                for ng_id in assigned_ids:
                    nic_dict['assigned_networks'].append(
                        {'id': ng_id, 'name': ngs_by_id[ng_id].name})
                    to_assign_ids.remove(ng_id)

            nics.append(nic_dict)

        if to_assign_ids:
            # Assign remaining networks to NIC #0
            # as all the networks must be assigned.
            # But network check will not pass if we get here.
            logger.warn(
                u"Cannot assign all networks appropriately for "
                u"node %r. Set all unassigned networks to the "
                u"interface %r",
                node.name,
                nics[0]['name']
            )
            for ng_id in to_assign_ids:
                nics[0].setdefault('assigned_networks', []).append(
                    {'id': ng_id, 'name': ngs_by_id[ng_id].name})
        return nics

    @classmethod
    def assign_networks_by_default(cls, node):
        cls.clear_assigned_networks(node)

        nics = dict((nic.id, nic) for nic in node.interfaces)
        def_set = cls.get_default_interfaces_configuration(node)
        for nic in def_set:
            if 'assigned_networks' in nic:
                ng_ids = [ng['id'] for ng in nic['assigned_networks']]
                nics[nic['id']].assigned_networks_list = list(
                    db().query(NetworkGroup).filter(
                        NetworkGroup.id.in_(ng_ids)))
        db().flush()

    @classmethod
    def get_cluster_networkgroups_by_node(cls, node):
        """Method for receiving cluster network groups by node.

        :param node: Node object.
        :type  node: Node
        :returns: List of network groups for cluster node belongs to.
        """
        if node.group_id:
            return db().query(NetworkGroup).filter_by(
                group_id=node.group_id,
            ).filter(
                NetworkGroup.name != 'fuelweb_admin'
            ).order_by(NetworkGroup.id).all()
        else:
            return node.cluster.network_groups

    @classmethod
    def get_node_networkgroups_ids(cls, node):
        """Get ids of all networks assigned to node's interfaces"""
        return [ng.id for nic in node.interfaces
                for ng in nic.assigned_networks_list]

    @classmethod
    def _get_admin_node_network_data(cls, node, admin_nw_groups_nodegroup_idx,
                                     ips_node_network_idx):
        net = IndexedData.get_admin_nw_group(admin_nw_groups_nodegroup_idx,
                                             node)
        net_cidr = IPNetwork(net.cidr)

        ips_key = IndexedData.ips_node_nw_group_key(node, net)
        node_admin_ips = ips_node_network_idx[ips_key]
        if node_admin_ips:
            ip_addr = node_admin_ips[0].ip_addr
            ip_addr = cls.get_ip_w_cidr_prefix_len(ip_addr, net)
        else:
            ip_addr = None

        return {
            'name': net.name,
            'cidr': net.cidr,
            'vlan': net.vlan_start,
            'ip': ip_addr,
            'netmask': str(net_cidr.netmask),
            'brd': str(net_cidr.broadcast),
            'gateway': net.gateway,
            'dev': cls.get_admin_interface(node).name
        }

    @classmethod
    def get_network_by_netname(cls, netname, networks):
        return filter(
            lambda n: n['name'] == netname, networks)[0]

    @classmethod
    def get_network_vlan(cls, net_db, cl_db):
        return net_db.vlan_start if not net_db.meta.get('ext_net_data') \
            else getattr(cl_db.network_config, net_db.meta['ext_net_data'][0])

    @classmethod
    def _get_network_data_with_ip(cls, node_db, interface, net, ip):
        return {
            'name': net.name,
            'cidr': net.cidr,
            'vlan': cls.get_network_vlan(net, node_db.cluster),
            'ip': cls.get_ip_w_cidr_prefix_len(ip.ip_addr, net),
            'netmask': str(IPNetwork(net.cidr).netmask),
            'brd': str(IPNetwork(net.cidr).broadcast),
            'gateway': net.gateway,
            'dev': interface.name}

    @classmethod
    def _get_network_data_wo_ip(cls, node_db, interface, net):
        return {'name': net.name,
                'cidr': net.cidr,
                'vlan': cls.get_network_vlan(net, node_db.cluster),
                'dev': interface.name}

    @classmethod
    def _get_networks_except_admin(cls, networks):
        return (net for net in networks
                if net.name != consts.NETWORKS.fuelweb_admin)

    @classmethod
    def get_node_networks(cls, node):
        cluster_db = node.cluster
        if cluster_db is None:
            # Node doesn't belong to any cluster, so it should not have nets
            return []

        network_data = []
        for interface in node.interfaces:
            networks_wo_admin = cls._get_networks_except_admin(
                interface.assigned_networks_list)
            for net in networks_wo_admin:
                ip = cls.get_ip_by_network_name(node, net.name)
                if ip is not None:
                    network_data.append(cls._get_network_data_with_ip(
                        node, interface, net, ip))
                else:
                    network_data.append(cls._get_network_data_wo_ip(
                        node, interface, net))

        admin_nw_groups_nodegroup_idx = \
            IndexedData.get_admin_networks_nodegroup_index()
        ips_node_network_idx = IndexedData.get_ips_node_nw_group_index(
            db().query(IPAddr).filter(IPAddr.node.in_((node.id,))))

        admin_network_data = cls._get_admin_node_network_data(
            node, admin_nw_groups_nodegroup_idx, ips_node_network_idx)
        network_data.append(admin_network_data)

        return network_data

    @classmethod
    def _get_network_data(cls, node, network_groups, interface,
                          ips_node_index):
        """Gets node network data from indexes

        :param node: node DB object
        :param network_groups: network groups DB objects list
        :param interface: DB nic or bond object
        :param ips_node_index: indexed ips by node id
        :return: list of network data dicts
        """
        result = []
        for net in network_groups:
            ip = None
            for cur_ip in ips_node_index[node.id]:
                if cur_ip.network == net.id and node.group_id == net.group_id:
                    ip = cur_ip
                    break

            if ip is not None:
                result.append(cls._get_network_data_with_ip(
                    node, interface, net, ip))
            else:
                result.append(cls._get_network_data_wo_ip(
                    node, interface, net))
        return result

    @classmethod
    def get_nodes_networks(cls, nodes):
        """High performance nodes networks data fetcher

        Uses indexed data.

        :param nodes: nodes DB objects
        :return: dict of {node_id: [network_data]}
        """
        result = {}
        nodes_ids = set(node.id for node in nodes)

        # Creating network groups index by network group id
        nw_groups_idx = IndexedData.get_network_groups_index(index_by='id')

        # Creating admin network groups index by nodegroup id
        admin_nw_groups_nodegroup_idx = \
            IndexedData.get_admin_networks_nodegroup_index()

        # Creating index for nodes nic ifaces
        nic_ifaces_idx = IndexedData.get_nic_ifaces_index(nodes)
        nic_ifaces_ids = set(IndexedData.extract_attr_from_dict_of_lists(
            nic_ifaces_idx))
        nw_groups_nic_idx = IndexedData.get_network_groups_nic_iface_index(
            nw_groups_idx, nic_ifaces_ids=nic_ifaces_ids)

        # Creating indexes for nodes bonds
        bonds_idx = IndexedData.get_bonds_index(nodes)
        bonds_ids = set(IndexedData.extract_attr_from_dict_of_lists(
            bonds_idx))
        nw_groups_bond_idx = IndexedData.get_network_groups_bond_index(
            nw_groups_idx, bonds_ids=bonds_ids)

        # Creating ips index by node id
        ips_node_index = IndexedData.get_ips_node_index(
            nodes_ids=nodes_ids)

        # Creating index for ips by node id and network id
        ips_node_network_idx = IndexedData.get_ips_node_nw_group_index(
            db().query(IPAddr).filter(IPAddr.node.in_(nodes_ids)))

        for node in nodes:
            if node.cluster_id is None:
                result[node.id] = []
                continue

            network_data = []

            for interface in nic_ifaces_idx[node.id]:
                network_groups = nw_groups_nic_idx[interface.id]
                networks_wo_admin = cls._get_networks_except_admin(
                    network_groups)

                nw_data = cls._get_network_data(node, networks_wo_admin,
                                                interface, ips_node_index)
                network_data.extend(nw_data)

            for interface in bonds_idx[node.id]:
                network_groups = nw_groups_bond_idx[interface.id]
                networks_wo_admin = cls._get_networks_except_admin(
                    network_groups)

                nw_data = cls._get_network_data(node, networks_wo_admin,
                                                interface, ips_node_index)
                network_data.extend(nw_data)

            admin_node_network = cls._get_admin_node_network_data(
                node, admin_nw_groups_nodegroup_idx, ips_node_network_idx)
            network_data.append(admin_node_network)

            result[node.id] = network_data

        return result

    @classmethod
    def _update_attrs(cls, node_data):
        node_db = db().query(Node).get(node_data['id'])
        is_ether = lambda x: x['type'] == consts.NETWORK_INTERFACE_TYPES.ether
        is_bond = lambda x: x['type'] == consts.NETWORK_INTERFACE_TYPES.bond
        interfaces = filter(is_ether, node_data['interfaces'])
        bond_interfaces = filter(is_bond, node_data['interfaces'])

        interfaces_db = node_db.nic_interfaces
        bond_interfaces_db = node_db.bond_interfaces
        for iface in interfaces:
            current_iface = filter(
                lambda i: i.id == iface['id'],
                interfaces_db
            )[0]
            # Remove all old network's assignment for this interface.
            db().query(NetworkNICAssignment).filter_by(
                interface_id=current_iface.id
            ).delete()
            for net in iface['assigned_networks']:
                net_assignment = NetworkNICAssignment()
                net_assignment.network_id = net['id']
                net_assignment.interface_id = current_iface.id
                db().add(net_assignment)
            if 'interface_properties' in iface:
                current_iface.interface_properties = \
                    iface['interface_properties']
            if 'offloading_modes' in iface:
                current_iface.offloading_modes = \
                    iface['offloading_modes']
        map(db().delete, bond_interfaces_db)
        db().commit()

        for bond in bond_interfaces:
            bond_db = NodeBondInterface()
            bond_db.node_id = node_db.id
            db().add(bond_db)
            bond_db.name = bond['name']
            if bond.get('bond_properties', {}).get('mode'):
                bond_db.mode = bond['bond_properties']['mode']
            else:
                bond_db.mode = bond['mode']
            bond_db.mac = bond.get('mac')
            bond_db.bond_properties = bond.get('bond_properties', {})
            bond_db.interface_properties = bond.get('interface_properties', {})
            db().commit()
            db().refresh(bond_db)

            # Add new network assignment.
            map(bond_db.assigned_networks_list.append,
                [db().query(NetworkGroup).get(ng['id']) for ng
                 in bond['assigned_networks']])
            # Add new slaves.
            for nic in bond['slaves']:
                bond_db.slaves.append(
                    db().query(NodeNICInterface).filter_by(
                        name=nic['name']
                    ).filter_by(
                        node_id=node_db.id
                    ).first()
                )

            bond_db.offloading_modes = bond.get('offloading_modes', {})

            db().commit()

        return node_db.id

    @classmethod
    def update_interfaces_info(cls, node, update_by_agent=False):
        """Update interfaces info

        In case of correct interfaces in meta field in node's model
        """
        try:
            cls.check_interfaces_correctness(node)
        except errors.InvalidInterfacesInfo as e:
            logger.debug("Cannot update interfaces: %s", e.message)
            return
        pxe_iface_name = cls._get_pxe_iface_name(node)
        for interface in node.meta["interfaces"]:
            # set 'pxe' property for appropriate iface
            interface['pxe'] = (interface['name'] == pxe_iface_name)
            # try to get interface by mac address
            interface_db = next((
                n for n in node.nic_interfaces
                if utils.is_same_mac(n.mac, interface['mac'])),
                None)

            # try to get interface instance by interface name. this protects
            # us from loosing nodes when some NICs was replaced with a new one
            interface_db = interface_db or next((
                n for n in node.nic_interfaces if n.name == interface['name']),
                None)

            if interface_db:
                cls.__update_existing_interface(interface_db, interface,
                                                update_by_agent)
            else:
                cls.__add_new_interface(node, interface)

        cls.__delete_not_found_interfaces(node, node.meta["interfaces"])
        if node.cluster:
            cls._remap_admin_network(node)

    @classmethod
    def _remap_admin_network(cls, node):
        """Check and remap Admin-pxe network when PXE interface is changed

        :param node: Node instance
        :return:     None
        """
        iface_mapped, iface_pxe = None, None
        for iface in node.interfaces:
            for n in iface.assigned_networks_list:
                if n.name == consts.NETWORKS.fuelweb_admin:
                    iface_mapped = iface
                    break
            if iface.type == consts.NETWORK_INTERFACE_TYPES.ether and \
                    iface.pxe:
                # set to bond by default because networks are mapped to bond
                # if it exists
                iface_pxe = iface.bond or iface

        if not iface_pxe:
            # shouldn't be raised as it's set in update_interfaces_info()
            raise errors.CanNotFindInterface(
                'Cannot find PXE interface for node: {0}'.format(
                    node.full_name))
        if iface_mapped == iface_pxe:
            return

        if iface_mapped:
            # clear old Admin-pxe mapping
            iface_mapped.assigned_networks_list = \
                [n for n in iface_mapped.assigned_networks_list
                 if n.name != consts.NETWORKS.fuelweb_admin]
        iface_pxe.assigned_networks_list.append(
            cls.get_admin_network_group(node.id))
        db().flush()

    @classmethod
    def check_interfaces_correctness(cls, node):
        """Check node interfaces:

        * interface list in meta field is not empty
        * at least one interface has ip which
          includes to admin subnet. It can happens in
          case if agent was running, but network
          interfaces were not configured yet.
        * there're no networks assigned to removed interface
        """
        if not node.meta:
            raise errors.InvalidInterfacesInfo(
                u'Meta field for node "%s" is empty', node.full_name)
        if not node.meta.get('interfaces'):
            raise errors.InvalidInterfacesInfo(
                u'meta["interfaces"] is empty for node "%s"',
                node.full_name)

        interfaces = node.meta['interfaces']
        for interface in interfaces:
            ip_addr = interface.get('ip')
            if cls.is_ip_belongs_to_admin_subnet(ip_addr, node.id) or \
                    utils.is_same_mac(interface['mac'], node.mac):
                break
        else:
            raise errors.InvalidInterfacesInfo(
                u'Cannot find interface with ip which '
                'includes to admin subnet "%s"' % node.full_name)

        # raise exception if an interface is about to remove,
        # but has assigned network and it's already deployed
        interfaces = [i['name'] for i in interfaces]
        for iface in node.nic_interfaces:
            if iface.name not in interfaces and iface.assigned_networks_list:
                raise errors.InvalidInterfacesInfo(
                    u'Could not remove interface "{0}", since it is assigned '
                    u'to one or more networks'.format(iface.name)
                )

    @classmethod
    def is_ip_belongs_to_admin_subnet(cls, ip_addr, node_id=None):
        admin_cidr = cls.get_admin_network_group(node_id).cidr
        if ip_addr and IPAddress(ip_addr) in IPNetwork(admin_cidr):
            return True
        return False

    @classmethod
    def __add_new_interface(cls, node, interface_attrs):
        interface = NodeNICInterface()
        interface.node_id = node.id
        cls.__set_interface_attributes(interface, interface_attrs)
        db().add(interface)
        db().flush()

    @classmethod
    def __update_existing_interface(cls, interface, interface_attrs,
                                    update_by_agent=False):
        cls.__set_interface_attributes(interface, interface_attrs,
                                       update_by_agent)
        db().flush()

    @classmethod
    def __set_interface_attributes(cls, interface, interface_attrs,
                                   update_by_agent=False):
        interface.name = interface_attrs['name']
        interface.mac = interface_attrs['mac']

        interface.current_speed = interface_attrs.get('current_speed')
        interface.max_speed = interface_attrs.get('max_speed')
        interface.ip_addr = interface_attrs.get('ip')
        interface.netmask = interface_attrs.get('netmask')
        interface.state = interface_attrs.get('state')
        interface.driver = interface_attrs.get('driver')
        interface.bus_info = interface_attrs.get('bus_info')
        interface.pxe = interface_attrs.get('pxe', False)
        if interface_attrs.get('interface_properties'):
            interface.interface_properties = \
                interface_attrs['interface_properties']
        elif not interface.interface_properties:
            interface.interface_properties = \
                cls.get_default_interface_properties()

        new_offloading_modes = interface_attrs.get('offloading_modes')
        old_modes_states = interface.\
            offloading_modes_as_flat_dict(interface.offloading_modes)
        if new_offloading_modes:
            if update_by_agent:
                for mode in new_offloading_modes:
                    if mode["name"] in old_modes_states:
                        mode["state"] = old_modes_states[mode["name"]]
            interface.offloading_modes = new_offloading_modes

    @classmethod
    def __delete_not_found_interfaces(cls, node, interfaces):
        interfaces_mac_addresses = map(
            lambda interface: interface['mac'].lower(), interfaces)

        interfaces_to_delete = db().query(NodeNICInterface).filter(
            NodeNICInterface.node_id == node.id
        ).filter(
            not_(NodeNICInterface.mac.in_(interfaces_mac_addresses))
        ).all()

        if interfaces_to_delete:
            mac_addresses = ' '.join(
                map(lambda i: i.mac, interfaces_to_delete))

            node_name = node.name or node.mac
            logger.info("Interfaces %s removed from node %s" % (
                mac_addresses, node_name))

            map(db().delete, interfaces_to_delete)
        db().flush()

    @classmethod
    def get_admin_ip_for_node(cls, node_id):
        """Returns first admin IP address for node"""
        admin_net_id = cls.get_admin_network_group_id(node_id=node_id)
        admin_ip = db().query(IPAddr).order_by(
            IPAddr.id
        ).filter_by(
            node=node_id
        ).filter_by(
            network=admin_net_id
        ).first()

        return getattr(admin_ip, 'ip_addr', None)

    @classmethod
    def get_admin_ips_for_interfaces(cls, node):
        """Returns mapping admin {"inteface name" => "admin ip"}"""
        admin_net_id = cls.get_admin_network_group_id(node)
        admin_ips = set([
            i.ip_addr for i in db().query(IPAddr).
            order_by(IPAddr.id).
            filter_by(node=node).
            filter_by(network=admin_net_id)])

        interfaces_names = sorted(set([
            interface.name for interface in node.interfaces]))

        return dict(zip(interfaces_names, admin_ips))

    @classmethod
    def _get_admin_network(cls, node):
        """Returns dict with admin network."""

        net = cls.get_admin_network_group(node_id=node)
        return {
            'id': net.id,
            'cidr': net.cidr,
            'name': net.name,
            'gateway': net.gateway,
            'vlan': net.vlan_start,
            'dev': cls.get_admin_interface(node).name
        }

    @classmethod
    def get_admin_interface(cls, node):
        try:
            return cls._get_interface_by_network_name(
                node, consts.NETWORKS.fuelweb_admin)
        except errors.CanNotFindInterface:
            logger.debug(u'Cannot find interface with assigned admin '
                         'network group on %s', node.full_name)

        for iface in node.nic_interfaces:
            if cls.is_ip_belongs_to_admin_subnet(iface.ip_addr, node.id):
                return iface

        logger.warning(u'Cannot find admin interface for node '
                       'return first interface: "%s"', node.full_name)
        return node.interfaces[0]

    @classmethod
    def _get_interface_by_network_name(cls, node, network_name):
        """Return network device by specified network name"""
        if not isinstance(node, Node):
            node = db().query(Node).get(node)
        for interface in node.interfaces:
            for network in interface.assigned_networks_list:
                if network.name == network_name:
                    return interface

        raise errors.CanNotFindInterface(
            u'Cannot find interface by name "{0}" for node: '
            '{1}'.format(network_name, node.full_name))

    @classmethod
    def get_ip_by_network_name(cls, node, network_name):
        for ip in node.ip_addrs:
            ng = ip.network_data
            if ng.name == network_name and ng.group_id == node.group_id:
                return ip
        return None

    @classmethod
    def get_end_point_ip(cls, cluster_id):
        cluster_db = objects.Cluster.get_by_uid(cluster_id)
        ip = None
        if cluster_db.is_ha_mode:
            nodegroup = objects.Cluster.get_controllers_node_group(cluster_db)
            ip = cls.assign_vip(nodegroup, "public")
        elif cluster_db.mode in ('singlenode', 'multinode'):
            controller = db().query(Node).filter_by(
                cluster_id=cluster_id
            ).filter(
                Node.roles.any('controller')
            ).first()

            public_net = filter(
                lambda network: network['name'] == 'public',
                controller.network_data)[0]

            if public_net.get('ip'):
                ip = public_net['ip'].split('/')[0]

        if not ip:
            raise errors.CanNotDetermineEndPointIP(
                u'Can not determine end point IP for cluster %s' %
                cluster_db.full_name)

        return ip

    @classmethod
    def get_horizon_url(cls, cluster_id):
        return 'http://%s/' % cls.get_end_point_ip(cluster_id)

    @classmethod
    def get_keystone_url(cls, cluster_id):
        return 'http://%s:5000/' % cls.get_end_point_ip(cluster_id)

    @classmethod
    def get_zabbix_url(cls, cluster):
        zabbix_node = ZabbixManager.get_zabbix_node(cluster)
        if zabbix_node is None:
            return None
        ip_cidr = cls.get_network_by_netname(
            'public', cls.get_node_networks(zabbix_node))['ip']
        ip = ip_cidr.split('/')[0]
        return 'http://{0}/zabbix'.format(ip)

    @classmethod
    def is_same_network(cls, ipaddress, ipnetwork):
        """Verifies that ipaddress belongs to network.

        :param ipaddress: example. 10.0.0.0
        :type ipaddress: str
        :param ipnetwork: example. 10.0.0.0/24
        :type ipnetwork: str
        :returns: bool
        """
        return IPAddress(ipaddress) in IPNetwork(ipnetwork)

    @classmethod
    def is_cidr_intersection(cls, cidr1, cidr2):
        """Checks intersection of two CIDRs (IPNetwork objects)"""
        return cidr2 in cidr1 or cidr1 in cidr2

    @classmethod
    def is_range_intersection(cls, range1, range2):
        """Checks intersection of IP ranges (IPNetwork or IPRange objects)"""
        return range1.first <= range2.last and range2.first <= range1.last

    @classmethod
    def get_node_interface_by_netname(cls, node_id, netname):
        iface = db().query(NodeNICInterface).join(
            (NetworkGroup, NodeNICInterface.assigned_networks_list)
        ).filter(
            NetworkGroup.name == netname
        ).filter(
            NodeNICInterface.node_id == node_id
        ).first()
        if iface:
            return iface

        return db().query(NodeBondInterface).join(
            (NetworkGroup, NodeBondInterface.assigned_networks_list)
        ).filter(
            NetworkGroup.name == netname
        ).filter(
            NodeBondInterface.node_id == node_id
        ).first()

    @classmethod
    def create_admin_network_group(cls, cluster_id, group_id):
        cluster_db = objects.Cluster.get_by_uid(cluster_id)
        admin_ng = cls.get_admin_network_group()
        new_admin = NetworkGroup(
            release=cluster_db.release.id,
            name='fuelweb_admin',
            cidr='9.9.9.0/24',
            gateway='9.9.9.1',
            group_id=group_id,
            vlan_start=None,
            meta=admin_ng.meta
        )
        db().add(new_admin)
        db().flush()

    @classmethod
    def create_network_group(cls, cluster, net, gid=None):
        """Method for creation of network groups for cluster.

        :param cluster: Cluster instance.
        :type  cluster: instance
        :param net: Network metadata
        :type  net: dict
        :param gid: Group ID
        :type  gid: integer
        :returns: None
        """
        group_id = gid or objects.Cluster.get_default_group(cluster).id
        cidr, gw = None, None
        if net.get("notation"):
            cidr = IPNetwork(net["cidr"]).cidr
            cidr_gw = str(cidr[1])
            if net.get('use_gateway'):
                if net["notation"] == 'cidr':
                    gw = cidr_gw
                elif net["notation"] == 'ip_ranges':
                    gw = net.get('gateway') or cidr_gw
        data = {
            'release': cluster.release.id,
            'name': net['name'],
            'cidr': str(cidr) if cidr else None,
            'gateway': gw,
            'group_id': group_id,
            'vlan_start': net.get('vlan_start'),
            'meta': net
        }
        objects.NetworkGroup.create(data)

    @classmethod
    def create_network_groups(cls, cluster, neutron_segment_type, gid=None):
        """Method for creation of network groups for cluster.

        :param cluster: Cluster instance.
        :type  cluster: instance
        :returns: None
        """
        networks_metadata = cluster.release.networks_metadata
        networks_list = networks_metadata[cluster.net_provider]["networks"]

        for net in networks_list:
            if "seg_type" in net \
                    and neutron_segment_type != net['seg_type']:
                continue
            cls.create_network_group(cluster, net, gid)

    @classmethod
    def update_networks(cls, network_configuration):
        if 'networks' in network_configuration:
            for ng in network_configuration['networks']:
                if ng['id'] == cls.get_admin_network_group_id():
                    continue

                ng_db = db().query(NetworkGroup).get(ng['id'])

                if 'meta' not in ng:
                    # there are no restrictions on update process if
                    # meta is not supplied
                    objects.NetworkGroup.update(ng_db, ng)
                    continue

                # only 'notation' and 'use_gateway' attributes is
                # allowed to be updated in network group metadata for
                # old clusters so here we updated it manually with data
                # which doesn't contain 'meta' key
                meta_to_update = {}

                for param in ('notation', 'use_gateway'):
                    if param in ng.get('meta', {}):
                        meta_to_update[param] = ng['meta'][param]

                # update particular keys in data
                objects.NetworkGroup.update_meta(
                    ng_db, meta_to_update
                )

                # preserve original input dict but remove 'meta' key
                # for proper update of the network group instance
                data_to_update = dict(ng)
                del data_to_update['meta']
                objects.NetworkGroup.update(ng_db, data_to_update)

    @classmethod
    def update(cls, cluster, network_configuration):
        cls.update_networks(network_configuration)

        if 'networking_parameters' in network_configuration:
            if cluster.is_locked:
                logger.warning("'network_parameters' are presented in update"
                               " data but they are locked after deployment."
                               " New values were ignored.")
                return
            for key, value in network_configuration['networking_parameters'] \
                    .items():
                setattr(cluster.network_config, key, value)
            db().flush()

    @classmethod
    def cluster_has_bonds(cls, cluster_id):
        return db().query(Node).filter(
            Node.cluster_id == cluster_id
        ).filter(
            Node.bond_interfaces.any()).count() > 0

    @classmethod
    def create_network_groups_and_config(cls, cluster, data):
        segmentation_type = None

        if cluster.net_provider == 'neutron':
            neutron_config = cls.create_neutron_config(
                cluster,
                data.get('net_segment_type'),
                data.get('net_l23_provider'))
            segmentation_type = neutron_config.segmentation_type
        elif cluster.net_provider == 'nova_network':
            cls.create_nova_network_config(cluster)

        cls.create_network_groups(cluster, segmentation_type)

    @classmethod
    def get_network_config_create_data(cls, cluster):
        data = {}
        if cluster.net_provider == consts.CLUSTER_NET_PROVIDERS.neutron:
            data['net_l23_provider'] = cluster.network_config.net_l23_provider
            data['net_segment_type'] = cluster.network_config.segmentation_type
        return data

    @classmethod
    def get_default_gateway(cls, node_id):
        """Returns GW from Admin network if it's set, else returns Admin IP"""
        return cls.get_admin_network_group(node_id).gateway \
            or settings.MASTER_IP

    @classmethod
    def get_networks_not_on_node(cls, node, networks=None):
        networks = networks or cls.get_node_networks(node)
        node_net = [(n['name'], n['cidr'])
                    for n in networks if n.get('cidr')]
        all_nets = [(n.name, n.cidr)
                    for n in node.cluster.network_groups if n.cidr]

        admin_net = cls.get_admin_network_group()
        all_nets.append((admin_net.name, admin_net.cidr))

        other_nets = set(all_nets) ^ set(node_net)
        output = {}
        for name, cidr in other_nets:
            if name not in output:
                output[name] = []
            output[name].append(cidr)

        return output

    @classmethod
    def get_lnx_bond_properties(cls, bond):
        properties = {'mode': bond.mode}
        properties.update(bond.bond_properties)
        to_drop = [k for k in properties.keys() if k.endswith('__')]
        map(properties.pop, to_drop)
        return properties

    @classmethod
    def get_iface_properties(cls, iface):
        properties = {}
        if iface.interface_properties.get('mtu'):
            properties['mtu'] = iface.interface_properties['mtu']
        if iface.interface_properties.get('disable_offloading'):
            properties['vendor_specific'] = {
                'disable_offloading':
                iface.interface_properties['disable_offloading']
            }
        if iface.offloading_modes:
            modified_offloading_modes = \
                cls._get_modified_offloading_modes(iface.offloading_modes)
            if modified_offloading_modes:
                properties['ethtool'] = {}
                properties['ethtool']['offload'] = \
                    modified_offloading_modes

        return properties

    @classmethod
    def _get_modified_offloading_modes(cls, offloading_modes):
        result = dict()
        for mode in offloading_modes:
            if mode['state'] is not None:
                result[mode['name']] = mode['state']
            if mode['sub'] and mode['state'] is not False:
                result.update(cls._get_modified_offloading_modes(mode['sub']))
        return result

    @classmethod
    def find_nic_assoc_with_ng(cls, node, network_group):
        """Will find iface on node that is associated with network_group.

        If interface is a part of bond - check network on that bond
        """
        for iface in node.nic_interfaces:
            assigned_networks = iface.assigned_networks_list
            if iface.bond:
                assigned_networks = iface.bond.assigned_networks_list
            if network_group in assigned_networks:
                return iface
        return None

    @classmethod
    def get_prohibited_admin_bond_modes(cls):
        """Returns prohibited bond modes for admin interface

        :returns: list of bond modes
        """
        # in experimental mode we don't prohibit any mode
        if 'experimental' in settings.VERSION['feature_groups']:
            return []
        return [consts.BOND_MODES.lacp_balance_tcp,
                consts.BOND_MODES.l_802_3ad]

    @classmethod
    def get_ip_w_cidr_prefix_len(cls, ip, network_group):
        """Returns IP with address space prefix, e.g. "10.20.0.1/24"""
        return "{0}/{1}".format(ip, IPNetwork(network_group.cidr).prefixlen)

    @classmethod
    def get_assigned_ips_by_network_id(cls, network_id):
        """Returns IPs related to network with provided ID"""
        return [x[0] for x in
                db().query(IPAddr.ip_addr).filter_by(
                    network=network_id)]


class AllocateVIPs70Mixin(object):

    @classmethod
    def _build_advanced_vip_info(cls, vip_info, role, address):
        return {'network_role': role['id'],
                'namespace': vip_info.get('namespace'),
                'ipaddr': address,
                'node_roles': vip_info.get('node_roles',
                                           ['controller',
                                            'primary-controller'])}

    @classmethod
    def find_network_role_by_id(cls, cluster, role_id):
        """Returns network role for specified role id.

        :param cluster: Cluster instance
        :param role_id: Network role id
        :type role_id: str
        :return: Network role dict or None if not found
        """
        net_roles = objects.Cluster.get_network_roles(cluster)
        for role in net_roles:
            if role['id'] == role_id:
                return role
        return None

    @classmethod
    def get_end_point_ip(cls, cluster_id):
        cluster_db = objects.Cluster.get_by_uid(cluster_id)
        net_role = cls.find_network_role_by_id(cluster_db, 'public/vip')
        if not net_role:
            raise errors.CanNotDetermineEndPointIP(
                u'Can not determine end point IP for cluster {0}'.format(
                    cluster_db.full_name))
        node_group = objects.Cluster.get_controllers_node_group(cluster_db)
        net_group_mapping = cls.build_role_to_network_group_mapping(
            cluster_db, node_group.name)
        net_group = cls.get_network_group_for_role(
            net_role, net_group_mapping)
        return cls.assign_vip(node_group, net_group, vip_type='public')

    @classmethod
    def _assign_vips_for_net_groups(cls, cluster):
        # noderole -> nodegroup mapping
        #   is used for determine nodegroup where VIP should be allocated
        noderole_nodegroup = {}
        # nodegroup -> role-to-network mapping
        #   is used for determine role-to-network mapping that is needed
        #   for choosing proper network for VIP allocation
        nodegroup_networks = {}

        # iterate over all network roles, assign vip and yield information
        # about assignment
        for role in objects.Cluster.get_network_roles(cluster):
            properties = role.get('properties', {})
            for vip_info in properties.get('vip', ()):
                noderoles = tuple(vip_info.get('node_roles', ['controller']))

                # Since we're iterating over all VIP requests, we most
                # likely meet the same noderoles again and again. Let's
                # calculate node group just once, cache and use cached
                # value in order to reduce number of SQL queries.
                if noderoles not in noderole_nodegroup:
                    noderole_nodegroup[noderoles] = \
                        objects.Cluster.get_node_group(cluster, noderoles)
                nodegroup = noderole_nodegroup[noderoles]

                # Since different node roles may have the same node group,
                # it'd be ridiculous to build "role-to-network-group" mapping
                # each time we retrieve the group. So let's save mapping
                # in cache and retrieve it if necessary.
                if nodegroup.name not in nodegroup_networks:
                    nodegroup_networks[nodegroup.name] = \
                        cls.build_role_to_network_group_mapping(
                            cluster, nodegroup.name)

                net_group = cls.get_network_group_for_role(
                    role,
                    nodegroup_networks[nodegroup.name])
                vip_name = vip_info['name']

                # do allocation
                vip_addr = cls.assign_vip(nodegroup, net_group, vip_name)
                yield role, vip_info, vip_addr

    @classmethod
    def assign_vips_for_net_groups_for_api(cls, cluster):
        """Calls cls.assign_vip for all vips in network roles.

        Returns dict with vip definitions in API compatible format::

            {
                "vip_alias": "172.16.0.1"
            }

        :param cluster: Cluster instance
        :type  cluster: Cluster model
        :return: dict with vip definitions
        """
        vips = {}
        vips['vips'] = {}
        for role, vip_info, vip_addr in cls._assign_vips_for_net_groups(
                cluster):

            vip_name = vip_info['name']
            vips['vips'][vip_name] = cls._build_advanced_vip_info(vip_info,
                                                                  role,
                                                                  vip_addr)

            # Add obsolete configuration.
            # TODO(romcheg): Remove this in the 8.0 release
            alias = vip_info.get('alias')
            if alias:
                vips[alias] = vip_addr

        return vips

    @classmethod
    def assign_vips_for_net_groups(cls, cluster):
        """Calls cls.assign_vip for all vips in network roles.

        To be used for the output generation for orchestrator.
        Returns dict with vip definitions like::

            {
                "vip_name": {
                    "network_role": "public",
                    "namespace": "haproxy",
                    "ipaddr": "172.16.0.1"
                }
            }

        :param cluster: Cluster instance
        :type  cluster: Cluster model
        :return: dict with vip definitions
        """
        vips = {}
        for role, vip_info, vip_addr in cls._assign_vips_for_net_groups(
                cluster):
            vip_name = vip_info['name']
            vips[vip_name] = cls._build_advanced_vip_info(vip_info,
                                                          role,
                                                          vip_addr)
        return vips


class IndexedData(object):
    @staticmethod
    def build_index(collection, key_getter):
        """Builds index on collection by keys, returned by key_getter

        :param collection: source collection
        :param key_getter: function for getting index keys
        :return: dict of {key: collection_item}
        """
        return dict((key_getter(obj), obj) for obj in collection)

    @staticmethod
    def build_index_of_lists(collection, key_getter):
        """Builds index on collection by keys, returned by key_getter

        :param collection: source collection
        :param key_getter: function for getting index keys
        :return: dict of lists {key: [collection_items]}
        """
        result = defaultdict(list)
        for obj in collection:
            result[key_getter(obj)].append(obj)
        return result

    @staticmethod
    def extract_attr_from_dict_of_lists(
            d, attrgetter=operator.attrgetter('id')):
        """Extracts attributes from dict of object lists

        :param d: dict of {key: [items]}
        :param attrgetter: attribute getter applied for items
        :return: list of items attributes: [item1.attr, item2.attr, ...]
        """
        for objs in six.itervalues(d):
            for obj in objs:
                yield attrgetter(obj)

    @staticmethod
    def get_network_groups_index(names=None, index_by='group_id'):
        """Returns network groups indexed by 'index_by'

        :param names: list of network groups names to be filtered
        :param index_by: key for indexing
        :return: dict of {index_by: network group}
        """
        nw_groups = db().query(NetworkGroup)
        if names is not None:
            nw_groups = nw_groups.filter(
                NetworkGroup.name.in_(names))
        return IndexedData.build_index(
            nw_groups, operator.attrgetter(index_by))

    @staticmethod
    def get_admin_nw_group(admin_networks_index, node_db):
        """Returns admin network group for given node

        :param admin_networks_index: admin networks indexed by nodegroup id
        :param node_db: Node DB object
        :return: NetworkGroup DB object
        """
        node_admin_nw_group = (admin_networks_index.get(node_db.group_id) or
                               admin_networks_index.get(None))
        if node_admin_nw_group is None:
            raise errors.AdminNetworkNotFound()
        return node_admin_nw_group

    @staticmethod
    def get_nic_ifaces_index(nodes):
        """Returns nic interfaces indexed by node_id

        :param nodes: nodes DB objects
        :return: dict of lists {node_id: [nic interfaces]}
        """
        nodes_ids = set(n.id for n in nodes)
        nic_ifaces = db().query(NodeNICInterface).filter(
            NodeNICInterface.node_id.in_(nodes_ids))

        return IndexedData.build_index_of_lists(
            nic_ifaces, operator.attrgetter('node_id'))

    @staticmethod
    def get_bonds_index(nodes):
        """Returns bonds indexed by node_id

        :param nodes: nodes DB objects
        :return: dict of lists {node_id: [nic interfaces]}
        """
        nodes_ids = set(n.id for n in nodes)
        bonds = db().query(NodeBondInterface).filter(
            NodeNICInterface.node_id.in_(nodes_ids))

        return IndexedData.build_index_of_lists(
            bonds, operator.attrgetter('node_id'))

    @staticmethod
    def _ifaces_network_groups_index(network_groups_index, assignment_model,
                                     id_getter, ids=None):
        """Implementation of fetching network groups index

        Index can be built by nic iface or bond id

        :param network_groups_index: indexed by id network groups
        :param assignment_model: SQLAlchemy nic of bonds assignments model
        :param id_getter: index key getter
        :param ids: object ids to be filtered
        :return: dict of {id_getter: [network groups]}
        """
        assignments = db().query(assignment_model)
        if ids is not None:
            assignments = assignments.filter(
                id_getter(assignment_model).in_(ids)
            )
        result = defaultdict(list)
        for assignment in assignments:
            obj_id = id_getter(assignment)
            result[obj_id].append(
                network_groups_index[assignment.network_id])
        return result

    @staticmethod
    def get_network_groups_nic_iface_index(network_groups_index,
                                           nic_ifaces_ids=None):
        """Returns network groups indexed by nic iface id

        :param network_groups_index: network groups index by id
        :param nic_ifaces_ids: nic ifaces ids to be filtered
        :return: indexed network groups: {nic.id: [network groups]}
        """
        return IndexedData._ifaces_network_groups_index(
            network_groups_index, NetworkNICAssignment,
            operator.attrgetter('interface_id'), ids=nic_ifaces_ids)

    @staticmethod
    def get_network_groups_bond_index(network_groups_index,
                                      bonds_ids=None):
        """Returns network groups indexed by bond id

        :param network_groups_index: network groups index by id
        :param bonds_ids: nic bonds ids to be filtered
        :return: indexed network groups: {bond.id: [network groups]}
        """
        return IndexedData._ifaces_network_groups_index(
            network_groups_index, NetworkBondAssignment,
            operator.attrgetter('bond_id'), ids=bonds_ids)

    @staticmethod
    def get_ips_node_index(nodes_ids=None):
        """Returns ips indexed by node id

        :param nodes_ids: nodes ids to be filtered
        :return: dict of {node.id: [ips]}
        """
        ips = db().query(IPAddr)
        if nodes_ids is not None:
            ips = ips.filter(IPAddr.node.in_(nodes_ids))
        return IndexedData.build_index_of_lists(
            ips, operator.attrgetter('node'))

    @staticmethod
    def get_ips_node_nw_group_index(ips):
        """Returns ips indexed by node id and network id

        :param ips: ips DB objects to be indexed
        :return: dict of {node.id_network.id: [ips]}
        """

        def ip_key_getter(obj):
            return '{0}_{1}'.format(obj.node, obj.network)

        return IndexedData.build_index_of_lists(
            ips, ip_key_getter
        )

    @staticmethod
    def ips_node_nw_group_key(node, network):
        """Returns key for ips index for given node and network

        :param node: Node DB object
        :param network: network DB object
        :return: key for ips index
        """
        return '{0}_{1}'.format(node.id, network.id)

    @staticmethod
    def get_admin_networks_nodegroup_index():
        return IndexedData.get_network_groups_index(
            names=(consts.NETWORKS.fuelweb_admin,), index_by='group_id')
