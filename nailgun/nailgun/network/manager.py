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
from itertools import chain
from itertools import groupby
from itertools import ifilter
from itertools import imap
from itertools import islice

from netaddr import IPAddress
from netaddr import IPNetwork
from netaddr import IPRange
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import not_


from nailgun.db import db
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import IPAddr
from nailgun.db.sqlalchemy.models import IPAddrRange
from nailgun.db.sqlalchemy.models import NetworkAssignment
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import NodeNICInterface
from nailgun.errors import errors
from nailgun.logger import logger


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

        network_group.netmask = str(new_cidr.netmask)

        db().add(ip_range)
        db().commit()

    @classmethod
    def get_admin_network_group_id(cls, fail_if_not_found=True):
        '''Method for receiving Admin NetworkGroup ID.

        :param fail_if_not_found: Raise an error
        if admin network group is not found in database.
        :type  fail_if_not_found: bool
        :returns: Admin NetworkGroup ID or None.
        :raises: errors.AdminNetworkNotFound
        '''
        admin_ng = db().query(NetworkGroup).filter_by(
            name="fuelweb_admin"
        ).first()
        if not admin_ng and fail_if_not_found:
            raise errors.AdminNetworkNotFound()
        return admin_ng.id

    @classmethod
    def get_admin_network_group(cls, fail_if_not_found=True):
        '''Method for receiving Admin NetworkGroup.

        :param fail_if_not_found: Raise an error
        if admin network group is not found in database.
        :type  fail_if_not_found: bool
        :returns: Admin NetworkGroup or None.
        :raises: errors.AdminNetworkNotFound
        '''
        admin_ng = db().query(NetworkGroup).filter_by(
            name="fuelweb_admin"
        ).first()
        if not admin_ng and fail_if_not_found:
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
        db().commit()

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
        cluster = db().query(Cluster).get(cluster_id)
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
        ipranges = imap(
            lambda ir: IPRange(ir.first, ir.last),
            network.ip_ranges
        )
        for r in ipranges:
            if addr in r:
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

        admin_net_id = cls.get_admin_network_group_id(False)
        if admin_net_id:
            ips = ips.filter(
                not_(IPAddr.network == admin_net_id)
            )

        return ips.all()

    @classmethod
    def clear_all_allowed_networks(cls, node_id):
        node_db = db().query(Node).get(node_id)
        for nic in node_db.interfaces:
            while nic.allowed_networks:
                nic.allowed_networks.pop()
        db().commit()

    @classmethod
    def clear_assigned_networks(cls, node):
        for nic in node.interfaces:
            while nic.assigned_networks:
                nic.assigned_networks.pop()
        db().commit()

    @classmethod
    def get_cluster_networkgroups_by_node(cls, node):
        """Method for receiving cluster network groups by node.

        :param node: Node object.
        :type  node: Node
        :returns: List of network groups for cluster node belongs to.
        """
        return node.cluster.network_groups

    @classmethod
    def get_node_networks(cls, node_id):
        """Method for receiving network data for a given node.

        :param node_id: Node database ID.
        :type  node_id: int
        :returns: List of network info for node.
        """
        node_db = db().query(Node).get(node_id)
        cluster_db = node_db.cluster
        if cluster_db is None:
            # Node doesn't belong to any cluster, so it should not have nets
            return []

        ips = cls._get_ips_except_admin(node_id=node_id)
        network_data = []
        network_ids = []
        for ip in ips:
            net = db().query(NetworkGroup).get(ip.network)
            interface = cls._get_interface_by_network_name(
                node_db.id, net.name)

            if net.name == 'public':
                # Get prefix from netmask instead of cidr
                # for public network

                # Convert netmask to prefix
                prefix = str(IPNetwork(
                    '0.0.0.0/' + net.netmask).prefixlen)
                netmask = net.netmask
            else:
                prefix = str(IPNetwork(net.cidr).prefixlen)
                netmask = str(IPNetwork(net.cidr).netmask)

            network_data.append({
                'name': net.name,
                'vlan': net.vlan_start,
                'ip': ip.ip_addr + '/' + prefix,
                'netmask': netmask,
                'brd': str(IPNetwork(net.cidr).broadcast),
                'gateway': net.gateway,
                'dev': interface.name})
            network_ids.append(net.id)

        network_data.extend(
            cls._add_networks_wo_ips(cluster_db, network_ids, node_db))

        return network_data

    @classmethod
    def get_node_network_by_netname(cls, node_id, netname):
        networks = cls.get_node_networks(node_id)
        return filter(
            lambda n: n['name'] == netname, networks)[0]

    @classmethod
    def group_by_key_and_history(cls, values, key_func):
        response = defaultdict(list)
        for group, value in groupby(values, key_func):
            response[group].extend(list(value))
        return response

    @classmethod
    def get_grouped_ips_by_node(cls):
        """returns {node.id: generator([IPAddr1, IPAddr2])}
        """
        ips_db = cls._get_ips_except_admin(joined=True)
        return cls.group_by_key_and_history(ips_db, lambda ip: ip.node)

    @classmethod
    def get_networks_grouped_by_cluster(cls):
        networks = db().query(NetworkGroup).order_by(NetworkGroup.id).all()
        return cls.group_by_key_and_history(
            networks,
            lambda net: net.cluster_id)

    @classmethod
    def get_node_networks_optimized(cls, node_db, ips_db, networks):
        """Method for receiving data for a given node with db data provided
        as input
        @nodes_db - List of Node instances
        @ips_db - generator([IPAddr1, IPAddr2])
        """
        cluster_db = node_db.cluster
        if cluster_db is None:
            # Node doesn't belong to any cluster, so it should not have nets
            return []

        network_data = []
        network_ids = []
        for ip in ips_db:
            net = ip.network_data
            interface = cls._get_interface_by_network_name(
                node_db,
                net.name
            )

            # Get prefix from netmask instead of cidr
            # for public network
            if net.name == 'public':

                # Convert netmask to prefix
                prefix = str(IPNetwork(
                    '0.0.0.0/' + net.netmask).prefixlen)
                netmask = net.netmask
            else:
                prefix = str(IPNetwork(net.cidr).prefixlen)
                netmask = str(IPNetwork(net.cidr).netmask)

            network_data.append({
                'name': net.name,
                'vlan': net.vlan_start,
                'ip': ip.ip_addr + '/' + prefix,
                'netmask': netmask,
                'brd': str(IPNetwork(net.cidr).broadcast),
                'gateway': net.gateway,
                'dev': interface.name})
            network_ids.append(net.id)

        nets_wo_ips = [n for n in networks if n.id not in network_ids]

        for net in nets_wo_ips:
            interface = cls._get_interface_by_network_name(
                node_db,
                net.name
            )

            if net.name == 'fixed' and cluster_db.net_manager == 'VlanManager':
                continue
            network_data.append({
                'name': net.name,
                'vlan': net.vlan_start,
                'dev': interface.name})

        network_data.append(cls._get_admin_network(node_db))

        return network_data

    @classmethod
    def _add_networks_wo_ips(cls, cluster_db, network_ids, node_db):
        add_net_data = []
        # And now let's add networks w/o IP addresses
        nets = db().query(NetworkGroup).\
            filter(NetworkGroup.cluster_id == cluster_db.id)
        if network_ids:
            nets = nets.filter(not_(NetworkGroup.id.in_(network_ids)))

        # For now, we pass information about all networks,
        #    so these vlans will be created on every node we call this func for
        # However it will end up with errors if we precreate vlans in VLAN mode
        #   in fixed network. We are skipping fixed nets in Vlan mode.
        for net in nets.order_by(NetworkGroup.id).all():
            interface = cls._get_interface_by_network_name(
                node_db,
                net.name
            )

            if net.name == 'fixed' and cluster_db.net_manager == 'VlanManager':
                continue
            add_net_data.append({
                'name': net.name,
                'vlan': net.vlan_start,
                'dev': interface.name})

        add_net_data.append(cls._get_admin_network(node_db))
        return add_net_data

    @classmethod
    def _update_attrs(cls, node_data):
        node_db = db().query(Node).get(node_data['id'])
        interfaces = node_data['interfaces']
        interfaces_db = node_db.interfaces
        for iface in interfaces:
            current_iface = filter(
                lambda i: i.id == iface['id'],
                interfaces_db
            )[0]
            # Remove all old network's assignment for this interface.
            db().query(NetworkAssignment).filter_by(
                interface_id=current_iface.id
            ).delete()
            for net in iface['assigned_networks']:
                net_assignment = NetworkAssignment()
                net_assignment.network_id = net['id']
                net_assignment.interface_id = current_iface.id
                db().add(net_assignment)
        db().commit()
        return node_db.id

    @classmethod
    def update_interfaces_info(cls, node):
        """Update interfaces in case of correct interfaces
        in meta field in node's model
        """
        try:
            cls.__check_interfaces_correctness(node)
        except errors.InvalidInterfacesInfo as e:
            logger.warn("Cannot update interfaces: %s" % str(e))
            return

        for interface in node.meta["interfaces"]:
            interface_db = db().query(NodeNICInterface).filter_by(
                mac=interface['mac']).first()
            if interface_db:
                cls.__update_existing_interface(interface_db.id, interface)
            else:
                cls.__add_new_interface(node, interface)

        cls.__delete_not_found_interfaces(node, node.meta["interfaces"])

    @classmethod
    def __check_interfaces_correctness(cls, node):
        """Check that
        * interface list in meta field is not empty
        * at least one interface has ip which
          includes to admin subnet. It can happens in
          case if agent was running, but network
          interfaces were not configured yet.
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

        if not admin_interface:
            raise errors.InvalidInterfacesInfo(
                u'Cannot find interface with ip which '
                'includes to admin subnet "%s"' % node.full_name)

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
        db().commit()
        node.interfaces.append(interface)

    @classmethod
    def __update_existing_interface(cls, interface_id, interface_attrs):
        interface = db().query(NodeNICInterface).get(interface_id)
        cls.__set_interface_attributes(interface, interface_attrs)
        db().commit()

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

    @classmethod
    def get_all_cluster_networkgroups(cls, node):
        if node.cluster:
            return db().query(NetworkGroup).filter_by(
                cluster_id=node.cluster.id
            ).order_by(NetworkGroup.id).all()
        return []

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
            'dev': node.admin_interface.name
        }

    @classmethod
    def _get_interface_by_network_name(cls, node, network_name):
        """Return network device which has appointed
        network with specified network name
        """
        if not isinstance(node, Node):
            node = db().query(Node).get(node)
        for interface in node.interfaces:
            for network in interface.assigned_networks:
                if network.name == network_name:
                    return interface

        raise errors.CanNotFindInterface(
            u'Cannot find interface by name "{0}" for node: '
            '{1}'.format(network_name, node.full_name))

    @classmethod
    def get_end_point_ip(cls, cluster_id):
        cluster_db = db().query(Cluster).get(cluster_id)
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
        return db().query(NodeNICInterface).join(
            (NetworkGroup, NodeNICInterface.assigned_networks)
        ).filter(
            NetworkGroup.name == netname
        ).filter(
            NodeNICInterface.node_id == node_id
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
    def update_cidr_from_gw_mask(cls, ng_db, ng):
        if ng.get('gateway') and ng.get('netmask'):
            from nailgun.network.checker import calc_cidr_from_gw_mask
            cidr = calc_cidr_from_gw_mask({'gateway': ng['gateway'],
                                           'netmask': ng['netmask']})
            if cidr:
                ng_db.cidr = str(cidr)
                ng_db.network_size = cidr.size
