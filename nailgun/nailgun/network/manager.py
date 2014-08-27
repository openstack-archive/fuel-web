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

from itertools import chain
from itertools import ifilter
from itertools import imap
from itertools import islice

from netaddr import IPAddress
from netaddr import IPNetwork
from netaddr import IPRange

from sqlalchemy.orm import joinedload
from sqlalchemy.sql import not_

from nailgun import objects

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import IPAddr
from nailgun.db.sqlalchemy.models import IPAddrRange
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import NetworkNICAssignment
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import NodeBondInterface
from nailgun.db.sqlalchemy.models import NodeNICInterface
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.utils.zabbix import ZabbixManager


class NetworkManager(object):

    @classmethod
    def update_range_mask_from_cidr(cls, network_group, cidr):
        """Update network ranges for cidr
        """
        db().query(IPAddrRange).filter_by(
            network_group_id=network_group.id).delete()

        new_cidr = IPNetwork(cidr)
        ip_range = IPAddrRange(
            network_group_id=network_group.id,
            first=str(new_cidr[2]),
            last=str(new_cidr[-2]))

        db().add(ip_range)
        db().commit()

    @classmethod
    def get_admin_network_group_id(cls):
        """Method for receiving Admin NetworkGroup ID.

        :type  fail_if_not_found: bool
        :returns: Admin NetworkGroup ID or None.
        :raises: errors.AdminNetworkNotFound
        """
        return cls.get_admin_network_group().id

    @classmethod
    def get_admin_network_group(cls):
        """Method for receiving Admin NetworkGroup.

        :type  fail_if_not_found: bool
        :returns: Admin NetworkGroup or None.
        :raises: errors.AdminNetworkNotFound
        """
        admin_ng = db().query(NetworkGroup).filter_by(
            name="fuelweb_admin"
        ).first()
        if not admin_ng:
            raise errors.AdminNetworkNotFound()
        return admin_ng

    @classmethod
    def cleanup_network_group(cls, nw_group):
        """Network group cleanup - deletes all IPs were assigned within
        the network group.

        :param nw_group: NetworkGroup object.
        :type  nw_group: NetworkGroup
        :returns: None
        """
        logger.debug("Deleting old IPs for network with id=%s, cidr=%s",
                     nw_group.id, nw_group.cidr)
        ips = db().query(IPAddr).filter(
            IPAddr.network == nw_group.id
        ).all()
        map(db().delete, ips)
        db().flush()

    @classmethod
    def assign_admin_ips(cls, node_id, num=1):
        """Method for assigning admin IP addresses to nodes.

        :param node_id: Node database ID.
        :type  node_id: int
        :param num: Number of IP addresses for node.
        :type  num: int
        :returns: None
        """
        admin_net_id = cls.get_admin_network_group_id()
        node_admin_ips = db().query(IPAddr).filter_by(
            node=node_id,
            network=admin_net_id
        ).all()

        if not node_admin_ips or len(node_admin_ips) < num:
            admin_net = db().query(NetworkGroup).get(admin_net_id)
            logger.debug(
                u"Trying to assign admin ips: node=%s count=%s",
                node_id,
                num - len(node_admin_ips)
            )
            free_ips = cls.get_free_ips(
                admin_net.id,
                num=num - len(node_admin_ips)
            )
            logger.info(len(free_ips))
            for ip in free_ips:
                ip_db = IPAddr(
                    node=node_id,
                    ip_addr=ip,
                    network=admin_net_id
                )
                db().add(ip_db)
            db().commit()

    @classmethod
    def assign_ips(cls, nodes_ids, network_name):
        """Idempotent assignment IP addresses to nodes.

        All nodes passed as first argument get IP address
        from network, referred by network_name.
        If node already has IP address from this network,
        it remains unchanged. If one of the nodes is the
        node from other cluster, this func will fail.

        :param node_ids: List of nodes IDs in database.
        :type  node_ids: list
        :param network_name: Network name
        :type  network_name: str
        :returns: None
        :raises: Exception, errors.AssignIPError
        """
        cluster_id = db().query(Node).get(nodes_ids[0]).cluster_id
        for node_id in nodes_ids:
            node = db().query(Node).get(node_id)
            if node.cluster_id != cluster_id:
                raise Exception(
                    u"Node id='{0}' doesn't belong to cluster_id='{1}'".format(
                        node_id,
                        cluster_id
                    )
                )

        network = db().query(NetworkGroup).\
            filter(NetworkGroup.cluster_id == cluster_id).\
            filter_by(name=network_name).first()

        if not network:
            raise errors.AssignIPError(
                u"Network '%s' for cluster_id=%s not found." %
                (network_name, cluster_id)
            )

        for node_id in nodes_ids:
            if network_name == 'public' and \
                    not objects.Node.should_have_public(
                    objects.Node.get_by_mac_or_uid(node_uid=node_id)):
                continue

            node_ips = imap(
                lambda i: i.ip_addr,
                cls._get_ips_except_admin(
                    node_id=node_id,
                    network_id=network.id
                )
            )
            # check if any of node_ips in required ranges

            ip_already_assigned = False

            for ip in node_ips:
                if cls.check_ip_belongs_to_net(ip, network):
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

            # IP address has not been assigned, let's do it
            logger.info(
                "Assigning IP for node '{0}' in network '{1}'".format(
                    node_id,
                    network_name
                )
            )
            free_ip = cls.get_free_ips(network.id)[0]
            ip_db = IPAddr(
                network=network.id,
                node=node_id,
                ip_addr=free_ip
            )
            db().add(ip_db)
            db().commit()

    @classmethod
    def assign_vip(cls, cluster_id, network_name):
        """Idempotent assignment VirtualIP addresses to cluster.
        Returns VIP for given cluster and network.

        It's required for HA deployment to have IP address
        not assigned to any of nodes. Currently we need one
        VIP per network in cluster. If cluster already has
        IP address from this network, it remains unchanged.
        If one of the nodes is the node from other cluster,
        this func will fail.

        :param cluster_id: Cluster database ID.
        :type  cluster_id: int
        :param network_name: Network name
        :type  network_name: str
        :returns: None
        :raises: Exception
        """
        cluster = objects.Cluster.get_by_uid(cluster_id)
        if not cluster:
            raise Exception(u"Cluster id='%s' not found" % cluster_id)

        network = db().query(NetworkGroup).\
            filter(NetworkGroup.cluster_id == cluster_id).\
            filter_by(name=network_name).first()

        if not network:
            raise Exception(u"Network '%s' for cluster_id=%s not found." %
                            (network_name, cluster_id))

        admin_net_id = cls.get_admin_network_group_id()
        cluster_ips = [ne.ip_addr for ne in db().query(IPAddr).filter_by(
            network=network.id,
            node=None
        ).filter(
            not_(IPAddr.network == admin_net_id)
        ).all()]
        # check if any of used_ips in required cidr: network.cidr
        ips_belongs_to_net = False
        for ip in cluster_ips:
            if cls.check_ip_belongs_to_net(ip, network):
                ips_belongs_to_net = True
                break

        if ips_belongs_to_net:
            vip = cluster_ips[0]
        else:
            # IP address has not been assigned, let's do it
            vip = cls.get_free_ips(network.id)[0]
            ne_db = IPAddr(network=network.id, ip_addr=vip)
            db().add(ne_db)
            db().commit()

        return vip

    @classmethod
    def _chunked_range(cls, iterable, chunksize=64):
        """We want to be able to iterate over iterable chunk by chunk.
        We instantiate iter object from itarable. We then yield
        iter instance slice in infinite loop. Iter slice starts
        from the last used position and finishes on the position
        which is offset with chunksize from the last used position.

        :param iterable: Iterable object.
        :type  iterable: iterable
        :param chunksize: Size of chunk to iterate through.
        :type  chunksize: int
        :yields: iterator
        :raises: StopIteration
        """
        it = iter(iterable)
        while True:
            s = islice(it, chunksize)
            # Here we check if iterator is not empty calling
            # next() method which raises StopInteration if
            # iter is empty. If iter is not empty we yield
            # iterator which is concatenation of fisrt element in
            # slice and the ramained elements.
            yield chain([s.next()], s)

    @classmethod
    def check_ip_belongs_to_net(cls, ip_addr, network):
        addr = IPAddress(ip_addr)
        for r in network.ip_ranges:
            if addr in IPRange(r.first, r.last):
                return True
        return False

    @classmethod
    def _iter_free_ips(cls, network_group):
        """Represents iterator over free IP addresses
        in all ranges for given Network Group
        """
        for ip_addr in ifilter(
            lambda ip: db().query(IPAddr).filter_by(
                ip_addr=str(ip)
            ).first() is None and not str(ip) == network_group.gateway,
            chain(*[
                IPRange(ir.first, ir.last)
                for ir in network_group.ip_ranges
            ])
        ):
            yield ip_addr

    @classmethod
    def get_free_ips(cls, network_group_id, num=1):
        """Returns list of free IP addresses for given Network Group
        """
        ng = db().query(NetworkGroup).get(network_group_id)
        free_ips = []
        for ip in cls._iter_free_ips(ng):
            free_ips.append(str(ip))
            if len(free_ips) == num:
                break
        if len(free_ips) < num:
            raise errors.OutOfIPs()
        return free_ips

    @classmethod
    def _get_ips_except_admin(cls, node_id=None,
                              network_id=None, joined=False):
        """Method for receiving IP addresses for node or network
        excluding Admin Network IP address.

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
            admin_net_id = cls.get_admin_network_group_id()
        except errors.AdminNetworkNotFound:
            admin_net_id = None
        if admin_net_id:
            ips = ips.filter(
                not_(IPAddr.network == admin_net_id)
            )

        return ips.all()

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
    def get_default_networks_assignment(cls, node):
        """Return default Networks-to-NICs assignment for given node based on
        networks metadata
        """
        nics = []
        ngs = node.cluster.network_groups + [cls.get_admin_network_group()]
        ngs_by_id = dict((ng.id, ng) for ng in ngs)
        # sort Network Groups ids by map_priority
        to_assign_ids = list(
            zip(*sorted(
                [[ng.id, ng.meta['map_priority']]
                 for ng in ngs],
                key=lambda x: x[1]))[0]
        )
        ng_ids = set(ng.id for ng in ngs)
        ng_wo_admin_ids = ng_ids ^ set([cls.get_admin_network_group_id()])
        for nic in node.nic_interfaces:
            nic_dict = {
                "id": nic.id,
                "name": nic.name,
                "mac": nic.mac,
                "max_speed": nic.max_speed,
                "current_speed": nic.current_speed,
                "type": nic.type,
            }

            if to_assign_ids:
                allowed_ids = \
                    ng_wo_admin_ids if nic != node.admin_interface else ng_ids
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
                    nic_dict.setdefault('assigned_networks', []).append(
                        {'id': ng_id, 'name': ngs_by_id[ng_id].name})
                    to_assign_ids.remove(ng_id)

            nics.append(nic_dict)

        if to_assign_ids:
            # Assign remaining networks to NIC #0
            # as all the networks must be assigned.
            # But network check will not pass if we get here.
            logger.warn(
                u"Cannot assign all networks appropriately for"
                u"node %r. Set all unassigned networks to the"
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
        def_set = cls.get_default_networks_assignment(node)
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
        return node.cluster.network_groups

    @classmethod
    def get_node_networkgroups_ids(cls, node):
        """Get ids of all networks assigned to node's interfaces
        """
        return [ng.id for nic in node.interfaces
                for ng in nic.assigned_networks_list]

    @classmethod
    def _get_admin_node_network(cls, node):
        net = cls.get_admin_network_group()
        net_cidr = IPNetwork(net.cidr)
        ip_addr = cls.get_admin_ip_for_node(node)
        return {
            'name': net.name,
            'vlan': net.vlan_start,
            'ip': "{0}/{1}".format(ip_addr, net_cidr.prefixlen),
            'netmask': str(net_cidr.netmask),
            'brd': str(net_cidr.broadcast),
            'gateway': net.gateway,
            'dev': node.admin_interface.name
        }

    @classmethod
    def get_node_network_by_netname(cls, node, netname):
        networks = cls.get_node_networks(node)
        networks.append(cls._get_admin_node_network(node))
        return filter(
            lambda n: n['name'] == netname, networks)[0]

    @classmethod
    def get_network_vlan(cls, net_db, cl_db):
        return net_db.vlan_start if not net_db.meta.get('ext_net_data') \
            else getattr(cl_db.network_config, net_db.meta['ext_net_data'][0])

    @classmethod
    def fixed_and_vlan_manager(cls, net, cluster_db):
        return net.name == 'fixed' \
            and cluster_db.network_config.net_manager == 'VlanManager'

    @classmethod
    def _get_network_data_with_ip(cls, node_db, interface, net, ip):
        prefix = str(IPNetwork(net.cidr).prefixlen)
        return {
            'name': net.name,
            'vlan': cls.get_network_vlan(net, node_db.cluster),
            'ip': ip.ip_addr + '/' + prefix,
            'netmask': str(IPNetwork(net.cidr).netmask),
            'brd': str(IPNetwork(net.cidr).broadcast),
            'gateway': net.gateway,
            'dev': interface.name}

    @classmethod
    def _get_network_data_wo_ip(cls, node_db, interface, net):
        return {'name': net.name,
                'vlan': cls.get_network_vlan(net, node_db.cluster),
                'dev': interface.name}

    @classmethod
    def _get_networks_except_admin(cls, networks):
        return (net for net in networks
                if net.name != 'fuelweb_admin')

    @classmethod
    def get_node_networks(cls, node_db):
        cluster_db = node_db.cluster
        if cluster_db is None:
            # Node doesn't belong to any cluster, so it should not have nets
            return []

        network_data = []
        for interface in node_db.interfaces:
            networks_wo_admin = cls._get_networks_except_admin(
                interface.assigned_networks_list)
            for net in networks_wo_admin:
                ip = cls._get_ip_by_network_name(node_db, net.name)
                if ip is not None:
                    network_data.append(cls._get_network_data_with_ip(
                        node_db, interface, net, ip))
                else:
                    if not cls.fixed_and_vlan_manager(net, cluster_db):
                        network_data.append(cls._get_network_data_wo_ip(
                            node_db, interface, net))

        network_data.append(cls._get_admin_network(node_db))

        return network_data

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
        map(db().delete, bond_interfaces_db)
        db().commit()

        for bond in bond_interfaces:
            bond_db = NodeBondInterface()
            bond_db.node_id = node_db.id
            db().add(bond_db)
            bond_db.name = bond['name']
            bond_db.mode = bond['mode']
            bond_db.mac = bond.get('mac')
            bond_db.flags = bond.get('flags', {})
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
            db().commit()

        return node_db.id

    @classmethod
    def update_interfaces_info(cls, node):
        """Update interfaces in case of correct interfaces
        in meta field in node's model
        """
        try:
            cls.check_interfaces_correctness(node)
        except errors.InvalidInterfacesInfo as e:
            logger.debug("Cannot update interfaces: %s", e.message)
            return

        for interface in node.meta["interfaces"]:
            # try to get interface by mac address
            interface_db = next((
                n for n in node.nic_interfaces if n.mac == interface['mac']),
                None)

            # try to get interface instance by interface name. this protects
            # us from loosing nodes when some NICs was replaced with a new one
            interface_db = interface_db or next((
                n for n in node.nic_interfaces if n.name == interface['name']),
                None)

            if interface_db:
                cls.__update_existing_interface(interface_db.id, interface)
            else:
                cls.__add_new_interface(node, interface)

        cls.__delete_not_found_interfaces(node, node.meta["interfaces"])

    @classmethod
    def check_interfaces_correctness(cls, node):
        """Check that
        * interface list in meta field is not empty
        * at least one interface has ip which
          includes to admin subnet. It can happens in
          case if agent was running, but network
          interfaces were not configured yet.
        * there're no networks assigned to removed interface
        """
        if not node.meta:
            raise errors.InvalidInterfacesInfo(
                u'Meta field for node "%s" is empty' % node.full_name)
        if not node.meta.get('interfaces'):
            raise errors.InvalidInterfacesInfo(
                u'Cannot find interfaces field "%s" in meta' % node.full_name)

        interfaces = node.meta['interfaces']
        admin_interface = None
        for interface in interfaces:
            ip_addr = interface.get('ip')
            if cls.is_ip_belongs_to_admin_subnet(ip_addr):
                # Interface was founded
                admin_interface = interface
                break
            elif interface['mac'].lower() == node.mac:
                admin_interface = interface
                break

        if not admin_interface:
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
    def is_ip_belongs_to_admin_subnet(cls, ip_addr):
        admin_cidr = cls.get_admin_network_group().cidr
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
    def __update_existing_interface(cls, interface_id, interface_attrs):
        interface = db().query(NodeNICInterface).get(interface_id)
        cls.__set_interface_attributes(interface, interface_attrs)
        db().add(interface)
        db().flush()

    @classmethod
    def __set_interface_attributes(cls, interface, interface_attrs):
        interface.name = interface_attrs['name']
        interface.mac = interface_attrs['mac']

        interface.current_speed = interface_attrs.get('current_speed')
        interface.max_speed = interface_attrs.get('max_speed')
        interface.ip_addr = interface_attrs.get('ip')
        interface.netmask = interface_attrs.get('netmask')
        interface.state = interface_attrs.get('state')

    @classmethod
    def __delete_not_found_interfaces(cls, node, interfaces):
        interfaces_mac_addresses = map(
            lambda interface: interface['mac'], interfaces)

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
    def get_admin_ip_for_node(cls, node):
        """Returns first admin IP address for node
        """
        admin_net_id = cls.get_admin_network_group_id()
        admin_ip = db().query(IPAddr).order_by(
            IPAddr.id
        ).filter_by(
            node=node.id
        ).filter_by(
            network=admin_net_id
        ).first()
        return admin_ip.ip_addr

    @classmethod
    def get_admin_ips_for_interfaces(cls, node):
        """Returns mapping admin {"inteface name" => "admin ip"}
        """
        admin_net_id = cls.get_admin_network_group_id()
        admin_ips = set([
            i.ip_addr for i in db().query(IPAddr).
            order_by(IPAddr.id).
            filter_by(node=node.id).
            filter_by(network=admin_net_id)])

        interfaces_names = sorted(set([
            interface.name for interface in node.interfaces]))

        return dict(zip(interfaces_names, admin_ips))

    @classmethod
    def _get_admin_network(cls, node):
        """Returns dict with admin network."""
        return {
            'name': 'admin',
            'dev': cls.get_admin_interface(node).name
        }

    @classmethod
    def get_admin_interface(cls, node):
        try:
            return cls._get_interface_by_network_name(
                node, 'fuelweb_admin')
        except errors.CanNotFindInterface:
            logger.debug(u'Cannot find interface with assigned admin '
                         'network group on %s', node.full_name)

        for interface in node.nic_interfaces:
            if cls.is_ip_belongs_to_admin_subnet(interface.ip_addr):
                return interface

        logger.warning(u'Cannot find admin interface for node '
                       'return first interface: "%s"', node.full_name)
        return node.interfaces[0]

    @classmethod
    def _get_interface_by_network_name(cls, node, network_name):
        """Return network device which has appointed
        network with specified network name
        """
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
    def _get_ip_by_network_name(cls, node, network_name):
        for ip in node.ip_addrs:
            if ip.network_data.name == network_name:
                return ip
        return None

    @classmethod
    def get_end_point_ip(cls, cluster_id):
        cluster_db = objects.Cluster.get_by_uid(cluster_id)
        ip = None
        if cluster_db.is_ha_mode:
            ip = cls.assign_vip(cluster_db.id, "public")
        elif cluster_db.mode in ('singlenode', 'multinode'):
            controller = db().query(Node).filter_by(
                cluster_id=cluster_id
            ).filter(Node.role_list.any(name='controller')).first()

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
        ip_cidr = cls.get_node_network_by_netname(
            zabbix_node, 'public'
        )['ip']
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
        """Checks intersection of two CIDRs (IPNetwork objects)
        """
        return cidr2 in cidr1 or cidr1 in cidr2

    @classmethod
    def is_range_intersection(cls, range1, range2):
        """Checks intersection of two IP ranges (IPNetwork or IPRange objects)
        """
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
    def _set_ip_ranges(cls, network_group_id, ip_ranges):
        # deleting old ip ranges
        db().query(IPAddrRange).filter_by(
            network_group_id=network_group_id).delete()

        for r in ip_ranges:
            new_ip_range = IPAddrRange(
                first=r[0],
                last=r[1],
                network_group_id=network_group_id)
            db().add(new_ip_range)
        db().commit()

    @classmethod
    def create_network_groups(cls, cluster_id, neutron_segment_type):
        """Method for creation of network groups for cluster.

        :param cluster_id: Cluster database ID.
        :type  cluster_id: int
        :returns: None
        """
        cluster_db = objects.Cluster.get_by_uid(cluster_id)
        networks_metadata = cluster_db.release.networks_metadata
        networks_list = networks_metadata[cluster_db.net_provider]["networks"]
        used_nets = [IPNetwork(cls.get_admin_network_group().cidr)]

        def check_range_in_use_already(cidr_range):
            for n in used_nets:
                if cls.is_range_intersection(n, cidr_range):
                    logger.warn("IP range {0} is in use already".format(
                        cidr_range))
                    break
            used_nets.append(cidr_range)

        for net in networks_list:
            if "seg_type" in net \
                    and neutron_segment_type != net['seg_type']:
                continue
            vlan_start = net.get("vlan_start")
            cidr, gw, cidr_gw = None, None, None
            if net.get("notation"):
                if net.get("cidr"):
                    cidr = IPNetwork(net["cidr"]).cidr
                    cidr_gw = str(cidr[1])
                if net["notation"] == 'cidr' and cidr:
                    new_ip_range = IPAddrRange(
                        first=str(cidr[2]),
                        last=str(cidr[-2])
                    )
                    if net.get('use_gateway'):
                        gw = cidr_gw
                    else:
                        new_ip_range.first = cidr_gw
                    check_range_in_use_already(cidr)
                elif net["notation"] == 'ip_ranges' and net.get("ip_range"):
                    new_ip_range = IPAddrRange(
                        first=net["ip_range"][0],
                        last=net["ip_range"][1]
                    )
                    gw = net.get('gateway') or cidr_gw \
                        if net.get('use_gateway') else None
                    check_range_in_use_already(IPRange(new_ip_range.first,
                                                       new_ip_range.last))

            nw_group = NetworkGroup(
                release=cluster_db.release.id,
                name=net['name'],
                cidr=str(cidr) if cidr else None,
                gateway=gw,
                cluster_id=cluster_id,
                vlan_start=vlan_start,
                meta=net
            )
            db().add(nw_group)
            db().flush()
            if net.get("notation"):
                nw_group.ip_ranges.append(new_ip_range)
                db().flush()
                cls.cleanup_network_group(nw_group)

    @classmethod
    def update_networks(cls, cluster, network_configuration):
        if 'networks' in network_configuration:
            for ng in network_configuration['networks']:
                if ng['id'] == cls.get_admin_network_group_id():
                    continue

                ng_db = db().query(NetworkGroup).get(ng['id'])

                for key, value in ng.iteritems():
                    if key == "ip_ranges":
                        cls._set_ip_ranges(ng['id'], value)
                    else:
                        if key == 'cidr' and \
                                ng_db.meta.get("notation") == "cidr":
                            cls.update_range_mask_from_cidr(ng_db, value)

                        if key != 'meta':
                            setattr(ng_db, key, value)

                if ng_db.meta.get("notation"):
                    cls.cleanup_network_group(ng_db)
                objects.Cluster.add_pending_changes(ng_db.cluster, 'networks')

    @classmethod
    def update(cls, cluster, network_configuration):
        cls.update_networks(cluster, network_configuration)

        if 'networking_parameters' in network_configuration:
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
        cls.create_network_groups(cluster.id,
                                  data.get('net_segment_type'))
        if cluster.net_provider == 'neutron':
            cls.create_neutron_config(cluster,
                                      data.get('net_segment_type'),
                                      data.get('net_l23_provider'))
        elif cluster.net_provider == 'nova_network':
            cls.create_nova_network_config(cluster)
