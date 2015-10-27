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


from itertools import combinations
from itertools import groupby
from itertools import product
import netaddr

from nailgun import consts
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun import objects
from nailgun.task.helpers import TaskHelper

from nailgun.objects.serializers.network_configuration \
    import NetworkConfigurationSerializer
from nailgun.objects.serializers.network_configuration \
    import NeutronNetworkConfigurationSerializer
from nailgun.objects.serializers.network_configuration \
    import NovaNetworkConfigurationSerializer


class NetworkCheck(object):

    def __init__(self, task, data):
        """Collect Network Groups data"""
        self.cluster = task.cluster
        self.task = task
        self.data = data
        self.net_man = objects.Cluster.get_network_manager(self.cluster)
        self.net_provider = self.cluster.net_provider
        admin_ng = objects.NetworkGroup.get_admin_network_group()
        fields = objects.NetworkGroup.fields()
        net = NetworkConfigurationSerializer.serialize_network_group(admin_ng,
                                                                     fields)
        # change Admin name for UI
        net.update(name='admin (PXE)')
        self.networks = [net]
        for ng in self.cluster.network_groups:
            net = NetworkConfigurationSerializer.serialize_network_group(
                ng,
                fields)
            self.networks.append(net)
        # merge with data['networks']
        for data_net in data.get('networks', []):
            for net in self.networks:
                if data_net['id'] == net['id']:
                    net.update(data_net)
                    if data_net.get('name') == consts.NETWORKS.fuelweb_admin:
                        net.update(name='admin (PXE)')
                    data_net.pop('meta', None)
                    break
        # get common networking parameters
        serializer = {
            consts.CLUSTER_NET_PROVIDERS.neutron:
            NeutronNetworkConfigurationSerializer,
            consts.CLUSTER_NET_PROVIDERS.nova_network:
            NovaNetworkConfigurationSerializer
        }
        self.network_config = serializer[self.net_provider].\
            serialize_network_params(self.cluster)
        self.network_config.update(data.get('networking_parameters', {}))

        self.result = []
        self.err_msgs = []

    def expose_error_messages(self):
        TaskHelper.expose_network_check_error_messages(
            self.task,
            self.result,
            self.err_msgs)

    def check_untagged_intersection(self):
        """check if there are untagged networks on the same interface

        (both nova-net and neutron)
        """
        netw_untagged = lambda n: (n['vlan_start'] is None) \
            and (not n['meta'].get('ext_net_data')) \
            and (not n['meta'].get('neutron_vlan_range'))
        untagged_nets = dict([(n['id'], n['name']) for n in self.networks
                              if netw_untagged(n)])
        # check if nic have assign only one untagged network
        if len(untagged_nets) >= 2:
            logger.info(
                "Untagged networks found, "
                "checking intersection between them...")

            bond_interfaces = (
                objects.Cluster.get_bond_interfaces_for_all_nodes(
                    self.cluster,
                    untagged_nets.keys()))
            nic_interfaces = (
                objects.Cluster.get_nic_interfaces_for_all_nodes(
                    self.cluster,
                    untagged_nets.keys()))
            found_intersection = []
            all_interfaces = bond_interfaces + nic_interfaces
            for iface in all_interfaces:
                # network name is changed for Admin on UI
                nets = [[ng['name'] for ng in self.networks
                        if n.id == ng['id']][0]
                        for n in iface.assigned_networks_list]
                crossed_nets = set(nets) & set(untagged_nets.values())
                if len(crossed_nets) > 1:
                    err_net_names = ['"{0}"'.format(i)
                                     for i in crossed_nets]
                    found_intersection.append((objects.Node.get_by_mac_or_uid(
                        node_uid=iface.node_id).name,
                        err_net_names))

            if found_intersection:
                nodes_with_errors = [
                    u'{1} networks at node "{0}"'.format(
                        int_node,
                        ", ".join(int_nets)
                    ) for int_node, int_nets in found_intersection]
                self.err_msgs.append(
                    u"Some untagged networks are assigned to the same "
                    u"physical interface. You should assign them to "
                    u"different physical interfaces. Affected:\n{0}".format(
                        "\n".join(nodes_with_errors)))
                self.result.append({"ids": [],
                                    "errors": []})
        self.expose_error_messages()

    def check_network_address_spaces_intersection(self):
        """check intersection of address spaces for all networks (nova-net)"""
        nets_w_cidr = filter(lambda n: n['cidr'], self.networks)
        for ngs in combinations(nets_w_cidr, 2):
            addrs = [netaddr.IPNetwork(ngs[0]['cidr']).cidr,
                     netaddr.IPNetwork(ngs[1]['cidr']).cidr]
            if self.net_man.is_range_intersection(addrs[0], addrs[1]):
                self.err_msgs.append(
                    u"Address space intersection between "
                    "networks:\n{0}.".format(
                        ", ".join([ngs[0]['name'], ngs[1]['name']])
                    )
                )
                self.result.append({
                    "ids": [int(ngs[0]["id"]), int(ngs[1]["id"])],
                    "errors": ["cidr"]
                })
        # Check for intersection with 'fixed' networks
        fixed_cidr = netaddr.IPNetwork(
            self.network_config['fixed_networks_cidr']).cidr
        for ng in nets_w_cidr:
            if self.net_man.is_range_intersection(
                    fixed_cidr, netaddr.IPNetwork(ng['cidr']).cidr):
                self.err_msgs.append(
                    u"Address space intersection between "
                    "networks:\nfixed, {0}.".format(ng['name'])
                )
                self.result.append({
                    "ids": [int(ng["id"])],
                    "errors": ["cidr"]
                })
        # Check for intersection with floating ranges
        nets_w_cidr = [n for n in self.networks
                       if n.get('cidr') and n['name'] !=
                       consts.NETWORKS.public]
        fl_ranges = [netaddr.IPRange(v[0], v[1])
                     for v in self.network_config['floating_ranges']]
        for net_vs_range in product(nets_w_cidr, fl_ranges):
            cidr = netaddr.IPNetwork(net_vs_range[0]['cidr']).cidr
            if self.net_man.is_range_intersection(cidr, net_vs_range[1]):
                self.err_msgs.append(
                    u"Address space intersection between floating range '{0}'"
                    " and '{1}' network.".format(
                        net_vs_range[1], net_vs_range[0]['name'])
                )
                self.result.append({
                    "ids": [int(net_vs_range[0]["id"])],
                    "errors": ["cidr", "floating_ranges"]
                })
        self.expose_error_messages()

    def check_public_floating_ranges_intersection(self):
        """Check public floating ranges intersection

        1. Check intersection of networks address spaces inside
        Public and Floating network
        2. Check that Public Gateway is in Public CIDR
        3. Check that Public IP ranges are in Public CIDR
        (nova-net)
        """
        pub = [ng for ng in self.networks
               if ng['name'] == consts.NETWORKS.public][0]
        # Check intersection of networks address spaces inside
        # Public and Floating network
        pub_ranges_err = False
        nets = {
            consts.NETWORKS.public: [
                netaddr.IPRange(v[0], v[1]) for v in pub['ip_ranges']
            ],
            'floating': [
                netaddr.IPRange(v[0], v[1])
                for v in self.network_config['floating_ranges']
            ]
        }
        for name, ranges in nets.iteritems():
            ids = [pub['id']] if name == consts.NETWORKS.public else []
            for npair in combinations(ranges, 2):
                if self.net_man.is_range_intersection(npair[0], npair[1]):
                    self.err_msgs.append(
                        u"Address space intersection between ranges "
                        u"of {0} network.".format(name)
                    )
                    self.result.append({"ids": ids,
                                        "errors": ["ip_ranges"]})
            for net in ranges:
                # Check intersection of public GW and pub/float IP ranges
                if netaddr.IPAddress(pub['gateway']) in net:
                    self.err_msgs.append(
                        u"Address intersection between "
                        u"public gateway and IP range "
                        u"of {0} network.".format(name)
                    )
                    self.result.append({"ids": ids,
                                        "errors": ["gateway",
                                                   "ip_ranges"]})
                # Check that public IP ranges are in public CIDR
                if name == consts.NETWORKS.public:
                    if net not in netaddr.IPNetwork(pub['cidr']) \
                            and not pub_ranges_err:
                        pub_ranges_err = True
                        self.err_msgs.append(
                            u"Public gateway and public ranges "
                            u"are not in one CIDR."
                        )
                        self.result.append({"ids": ids,
                                            "errors": ["gateway",
                                                       "ip_ranges"]})
        self.expose_error_messages()

        # Check intersection of public and floating ranges
        for npair in combinations(
                nets[consts.NETWORKS.public] + nets['floating'], 2):
            if self.net_man.is_range_intersection(npair[0], npair[1]):
                self.err_msgs.append(
                    u"Address space intersection between range "
                    u"of public network and floating range."
                )
                self.result.append({"ids": [pub['id']],
                                    "errors": ["ip_ranges"]})
        self.expose_error_messages()

    def check_vlan_ids_range_and_intersection(self):
        """Check vlan ids range and intersection

        1. check intersection of networks VLAN IDs ranges
        2. check networks VLAN ID ranges are in allowed range
        (nova-net)
        """
        tagged_nets = dict(
            (n['name'], [int(n['vlan_start']), 0])
            for n in self.networks
            if n['vlan_start'] is not None)
        if self.network_config['fixed_networks_vlan_start']:
            tagged_nets[consts.NETWORKS.fixed] = [
                self.network_config['fixed_networks_vlan_start'],
                self.network_config['fixed_networks_amount'] - 1]
        for name, vlan_range in tagged_nets.iteritems():
            # check VLAN ID range against [2-4094]
            if vlan_range[0] < 2 or vlan_range[0] + vlan_range[1] > 4094:
                self.err_msgs.append(
                    u"VLAN ID(s) is out of range for "
                    "{0} network.".format(name)
                )
                self.result.append({"ids": [int(n["id"]) for n in self.networks
                                            if n['name'] == name],
                                    "errors": ["vlan_start"]})
        for net in combinations(tagged_nets.keys(), 2):
            range1 = tagged_nets[net[0]]
            range2 = tagged_nets[net[1]]
            if range1[0] <= range2[0] + range2[1] \
                    and range2[0] <= range1[0] + range1[1]:
                self.err_msgs.append(
                    u"{0} networks use the same VLAN ID(s). "
                    "You should assign different VLAN IDs "
                    "to every network.".format(", ".join(net)))
                self.result.append({"ids": [int(n["id"])
                                            for n in self.networks
                                            if n['name'] in net],
                                    "errors": ["vlan_start"]})
        self.expose_error_messages()

    def check_networks_amount(self):
        """Check networks count

        1. check number of fixed networks is one in case of FlatDHCPManager
        2. check number of fixed networks fit in fixed CIDR and size of
        one fixed network
        (nova-net)
        """
        netmanager = self.network_config['net_manager']
        net_size = int(self.network_config['fixed_network_size'])
        net_amount = int(self.network_config['fixed_networks_amount'])
        net_cidr = netaddr.IPNetwork(
            self.network_config['fixed_networks_cidr'])
        if not netmanager == consts.NOVA_NET_MANAGERS.FlatDHCPManager and\
                net_size * net_amount > net_cidr.size:
            self.err_msgs.append(
                u"Number of fixed networks ({0}) doesn't fit into "
                u"fixed CIDR ({1}) and size of one fixed network "
                u"({2}).".format(net_amount, net_cidr, net_size)
            )
            self.result.append({"ids": [],
                                "errors": ["fixed_network_size",
                                           "fixed_networks_amount"]})
        self.expose_error_messages()

    def neutron_check_segmentation_ids(self):
        """Check neutron segmentation ids

        check networks VLAN IDs not in Neutron L2 private VLAN ID range
        for VLAN segmentation only
        (neutron)
        """
        tagged_nets = dict((n["name"], n["vlan_start"]) for n in filter(
            lambda n: (n["vlan_start"] is not None), self.networks))

        if tagged_nets:
            if self.task.cluster.network_config.segmentation_type == \
                    consts.NEUTRON_SEGMENT_TYPES.vlan:
                # check networks tags not in Neutron L2 private VLAN ID range
                vrange = self.network_config['vlan_range']
                net_intersect = [name for name, vlan in tagged_nets.iteritems()
                                 if vrange[0] <= vlan <= vrange[1]]
                if net_intersect:
                    nets_with_errors = ", ". \
                        join(net_intersect)
                    err_msg = u"VLAN tags of {0} network(s) intersect with " \
                              u"VLAN ID range defined for Neutron L2. " \
                              u"Networks VLAN tags must not intersect " \
                              u"with Neutron L2 VLAN ID range.". \
                        format(nets_with_errors)
                    raise errors.NetworkCheckError(err_msg)

    def neutron_check_network_address_spaces_intersection(self):
        """Check intersection of address spaces of all networks including admin

        (Neutron)
        """
        # check intersection of address ranges between all networks
        for ng1, ng2 in combinations(self.networks, 2):
            if ng1.get('cidr') and ng2.get('cidr'):
                # networks with the same name in different node groups maybe
                # considered as one shared network if they have equal CIDRs
                # and gateways
                if (ng1['group_id'] != ng2['group_id'] and
                        ng1['group_id'] is not None and
                        ng2['group_id'] is not None and
                        ng1['name'] == ng2['name'] and
                        ng1['gateway'] is not None and
                        ng1['gateway'] == ng2['gateway'] and
                        ng1['cidr'] == ng2['cidr']):
                    continue
                cidr1 = netaddr.IPNetwork(ng1['cidr'])
                cidr2 = netaddr.IPNetwork(ng2['cidr'])
                if self.net_man.is_cidr_intersection(cidr1, cidr2):
                    self.err_msgs.append(
                        u"Address space intersection "
                        u"between networks:\n{0}".format(
                            ", ".join([ng1['name'], ng2['name']])
                        )
                    )
                    self.result.append({
                        "ids": [int(ng1["id"]), int(ng2["id"])],
                        "errors": ["cidr"]
                    })
        self.expose_error_messages()

        # check Floating ranges belong to the same Public CIDR
        publics = filter(lambda ng: ng['name'] == consts.NETWORKS.public,
                         self.networks)
        public_cidrs = [netaddr.IPNetwork(p['cidr']).cidr for p in publics]

        floating_ip_ranges = [
            netaddr.IPRange(r1, r2)
            for r1, r2 in self.network_config['floating_ranges']]

        for cidr in public_cidrs:
            if all(range in cidr for range in floating_ip_ranges):
                break
        else:
            self.err_msgs.append(
                "Floating address ranges {0} are not in the same public CIDR."
                .format(', '.join(str(cidr) for cidr in floating_ip_ranges))
            )
            self.result = [{"ids": [],
                            "errors": ["cidr", "ip_ranges"]}]
        self.expose_error_messages()

        # Check intersection of networks address spaces inside
        # Public network
        for public in publics:
            public_cidr = netaddr.IPNetwork(public['cidr']).cidr
            public_gw = netaddr.IPAddress(public['gateway'])

            ranges = [netaddr.IPRange(start, end)
                      for start, end in public['ip_ranges']]
            ranges.extend(r for r in floating_ip_ranges if r in public_cidr)

            for npair in combinations(ranges, 2):
                if self.net_man.is_range_intersection(npair[0], npair[1]):
                    if (npair[0] in floating_ip_ranges or
                            npair[1] in floating_ip_ranges):
                        self.err_msgs.append(
                            u"Address space intersection between ranges "
                            u"of public and floating network."
                        )
                    else:
                        self.err_msgs.append(
                            u"Address space intersection between ranges "
                            u"of public network."
                        )
                    self.result.append({"ids": [int(public["id"])],
                                        "errors": ["ip_ranges"]})
            for net in ranges:
                # Check intersection of public GW and public IP ranges
                if public_gw in net:
                    self.err_msgs.append(
                        u"Address intersection between public gateway "
                        u"and IP range of public network."
                    )
                    self.result.append({"ids": [int(public["id"])],
                                        "errors": ["gateway", "ip_ranges"]})
                # Check that public IP ranges are in public CIDR
                if net not in public_cidr:
                    self.err_msgs.append(
                        u"Public gateway and public ranges "
                        u"are not in one CIDR."
                    )
                    self.result.append({"ids": [int(public["id"])],
                                        "errors": ["gateway", "ip_ranges"]})
        self.expose_error_messages()

        # check internal Gateway is in Internal CIDR
        cidr = netaddr.IPNetwork(self.network_config['internal_cidr'])
        gw = netaddr.IPAddress(self.network_config['internal_gateway'])
        if gw not in cidr:
            self.result.append({"ids": [],
                                "name": ["internal"],
                                "errors": ["gateway"]})
            self.err_msgs.append(
                u"Internal gateway {0} is not in internal "
                u"address space {1}.".format(str(gw), str(cidr))
            )
        for range in floating_ip_ranges:
            if self.net_man.is_range_intersection(range, cidr):
                self.result.append({"ids": [],
                                    "name": ["internal", "external"],
                                    "errors": ["cidr", "ip_ranges"]})
                self.err_msgs.append(
                    u"Intersection between internal CIDR {0} and floating "
                    u"range {1}.".format(cidr, range)
                )
        self.expose_error_messages()

    def neutron_check_l3_addresses_not_match_subnet_and_broadcast(self):
        """validate virtual l3 network address range and gateway

        check virtual l3 network address ranges and gateway don't intersect
        with subnetwork address and broadcast address (neutron)
        """
        ext_fl = self.network_config['floating_ranges'][0]
        ext_fl_r = netaddr.IPRange(ext_fl[0], ext_fl[1])

        pub = filter(lambda n: n['name'] == consts.NETWORKS.public,
                     self.networks)[0]
        pub_cidr = netaddr.IPNetwork(pub['cidr'])
        if pub_cidr.network in ext_fl_r or pub_cidr.broadcast in ext_fl_r:
            self.err_msgs.append(
                u"Neutron L3 external floating range [{0}] intersect with "
                u"either subnet address or broadcast address "
                u"of public network.".format(str(ext_fl_r))
            )
            self.result.append({"ids": [],
                                "name": ["external"],
                                "errors": ["ip_ranges"]})

        int_cidr = netaddr.IPNetwork(self.network_config['internal_cidr']).cidr
        int_gw = netaddr.IPAddress(self.network_config['internal_gateway'])
        if int_gw == int_cidr.network or int_gw == int_cidr.broadcast:
            self.err_msgs.append(
                u"Neutron L3 internal network gateway address is equal to "
                u"either subnet address or broadcast address of the network."
            )
            self.result.append({"ids": [],
                                "name": ["internal"],
                                "errors": ["gateway"]})

        if objects.Cluster.is_component_enabled(self.cluster, 'ironic'):
            bare_net = self.network_config['baremetal_range']
            bare_net_range = netaddr.IPRange(bare_net[0], bare_net[1])
            bare_gw = netaddr.IPAddress(
                self.network_config['baremetal_gateway'])

            if bare_gw in bare_net_range:
                self.err_msgs.append(
                    u"Neutron L3 address intersection between Ironic gateway "
                    u"and Ironic IP range."
                )
                self.result.append({"ids": [],
                                    "name": ["baremetal"],
                                    "errors": ["gateway", "ip_ranges"]})

        self.expose_error_messages()

    def _get_net_range_for_ip(self, ip, net):
        """Returns the first network's IP range that contains given IP."""
        if net.get('ip_ranges'):
            for r in net['ip_ranges']:
                ipr = netaddr.IPRange(r[0], r[1])
                if ip in ipr:
                    return ipr

    def neutron_check_gateways(self):
        """Check that gateways are set if non-default node groups are used."""
        if objects.NodeGroupCollection.get_by_cluster_id(
                self.cluster.id).count() < 2:
            return
        for net in self.networks:
            if net['meta']['notation'] in (
                    consts.NETWORK_NOTATION.cidr,
                    consts.NETWORK_NOTATION.ip_ranges):
                cidr = netaddr.IPNetwork(net['cidr'])
                if net['gateway'] is not None:
                    gw = netaddr.IPAddress(net['gateway'])
                    # broadcast and net address intersection is checked by
                    # check_network_addresses_not_match_subnet_and_broadcast
                    if gw in cidr:
                        ip_range = self._get_net_range_for_ip(gw, net)
                        if ip_range is not None:
                            self.err_msgs.append(
                                u"Gateway address belongs to the network's "
                                u"IP range [{0}].".format(ip_range)
                            )
                        self.result.append(
                            {"ids": [net['id']], "errors": ["gateway"]}
                        )
                    else:
                        self.err_msgs.append(
                            u"Gateway address does not belong to the network."
                        )
                        self.result.append(
                            {"ids": [net['id']], "errors": ["gateway"]}
                        )
                else:
                    self.err_msgs.append(
                        u"Gateway is not set for network."
                    )
                    self.result.append(
                        {"ids": [net['id']], "errors": ["gateway"]}
                    )
        self.expose_error_messages()

    def check_network_classes_exclude_loopback(self):
        """Check if address space is in real world addresses space

        1. check network address space lies inside A,B or C network class
        address space
        2. check network address space doesn't lie inside loopback
        address space
        (both neutron and nova-net)
        """
        for n in self.networks:
            if n.get('cidr'):
                cidr = netaddr.IPNetwork(n['cidr']).cidr
                if cidr in netaddr.IPNetwork('224.0.0.0/3'):
                    self.err_msgs.append(
                        u"{0} network address space does not belong to "
                        u"A, B, C network classes. It must belong to either "
                        u"A, B or C network class.".format(n["name"])
                    )
                    self.result.append({"ids": [int(n["id"])],
                                        "errors": ["cidr", "ip_ranges"]})
                elif cidr in netaddr.IPNetwork('127.0.0.0/8'):
                    self.err_msgs.append(
                        u"{0} network address space is inside loopback range "
                        u"(127.0.0.0/8). It must have no intersection with "
                        u"loopback range.".format(n["name"])
                    )
                    self.result.append({"ids": [int(n["id"])],
                                        "errors": ["cidr", "ip_ranges"]})
        self.expose_error_messages()

    def check_network_addresses_not_match_subnet_and_broadcast(self):
        """Network shouldn't intersect with subnetwork and broadcast

        check network address ranges and gateway don't intersect with
        subnetwork address and broadcast address (both neutron and nova-net)
        """
        for n in self.networks:
            if n['meta']['notation'] == 'ip_ranges':
                cidr = netaddr.IPNetwork(n['cidr']).cidr
                if n.get('gateway'):
                    gw = netaddr.IPAddress(n['gateway'])
                    if gw == cidr.network or gw == cidr.broadcast:
                        self.err_msgs.append(
                            u"{0} network gateway address is equal to either "
                            u"subnet address or broadcast address "
                            u"of the network.".format(n["name"])
                        )
                        self.result.append({"ids": [int(n["id"])],
                                            "errors": ["gateway"]})
                if n.get('ip_ranges'):
                    for r in n['ip_ranges']:
                        ipr = netaddr.IPRange(r[0], r[1])
                        if cidr.network in ipr or cidr.broadcast in ipr:
                            self.err_msgs.append(
                                u"{0} network IP range [{1}] intersect with "
                                u"either subnet address or broadcast address "
                                u"of the network.".format(n["name"], str(ipr))
                            )
                            self.result.append({"ids": [int(n["id"])],
                                                "errors": ["ip_ranges"]})
        flt_range = self.network_config['floating_ranges']
        for r in flt_range:
            ipr = netaddr.IPRange(r[0], r[1])
            if cidr.network in ipr or cidr.broadcast in ipr:
                self.err_msgs.append(
                    u"{0} network floating IP range [{1}] intersect "
                    u"with either subnet address or broadcast address "
                    u"of the network.".format(n["name"], str(ipr))
                )
                self.result.append({"ids": [int(n["id"])],
                                    "errors": ["ip_ranges"]})
        self.expose_error_messages()

    def check_bond_slaves_speeds(self):
        """check bond slaves speeds are equal"""
        for node in self.cluster.nodes:
            for bond in node.bond_interfaces:
                slaves_speed = set(
                    [slave.current_speed for slave in bond.slaves])
                if len(slaves_speed) != 1 or slaves_speed.pop() is None:
                    warn_msg = u"Node '{0}': interface '{1}' slave NICs " \
                        u"have different or unrecognized speeds". \
                        format(node.name, bond.name)
                    logger.warn(warn_msg)
                    self.err_msgs.append(warn_msg)

    def check_dns_servers_ips(self):
        """check DNS servers IPs are distinct"""
        ips = self.network_config['dns_nameservers']
        if len(set(ips)) < len(ips):
            self.err_msgs.append(
                u"DNS servers IPs have to be distinct."
            )
            self.result.append({"ids": [],
                                "errors": ['dns_nameservers']})
            self.expose_error_messages()

    def check_calculated_network_cidr(self):
        """Check calculated networks CIDRs are equal to values set by user

        E.g. when user set CIDR to "10.20.30.0/16" it will be calculated as
        "10.20.0.0/16". So, this helps to avoid some user errors while entering
        network parameters.
        """
        nets_w_cidr = filter(lambda n: n['cidr'], self.networks)
        for ng in nets_w_cidr:
            calc_cidr_str = str(netaddr.IPNetwork(ng['cidr']).cidr)
            if calc_cidr_str != ng['cidr']:
                self.err_msgs.append(
                    u"Calculated CIDR ({0}) is different from value ({1}) "
                    u"set by user for network:\n{2}.".format(
                        calc_cidr_str, ng['cidr'], ng['name'])
                )
                self.result.append({
                    "ids": [int(ng["id"])],
                    "errors": ["cidr"]
                })
        self.expose_error_messages()

    def check_vlan_ids_intersection(self):
        """Networks VLAN IDs should not intersect for any node's interface."""
        if self.cluster.network_config.configuration_template is not None:
            # TODO(akasatkin) checking of network templates to be considered
            return

        tagged_nets = dict((n["id"], n["vlan_start"]) for n in filter(
            lambda n: (n["vlan_start"] is not None), self.networks))

        # nothing to check
        if len(tagged_nets) < 2:
            return

        nodes_networks = \
            objects.Cluster.get_networks_to_interfaces_mapping_on_all_nodes(
                self.cluster)

        # first, group by hostname
        for node_name, data in groupby(nodes_networks, lambda x: x[0]):
            # then group by interface name for particular node
            for if_name, nic_nets in groupby(data, lambda x: x[1]):
                net_ids = [net_id
                           for _, _, net_id in nic_nets
                           if net_id in tagged_nets]
                if len(net_ids) < 2:
                    # no more than 1 tagged network is on the interface
                    continue
                vlan_ids = [tagged_nets[n] for n in net_ids]
                if len(set(vlan_ids)) < len(vlan_ids):
                    # some VLAN IDs are not unique for this interface
                    seen_vlan_ids = set()
                    duplicate_net_ids = set()
                    for idx in range(len(vlan_ids)):
                        if vlan_ids[idx] in seen_vlan_ids:
                            duplicate_net_ids.add(net_ids[idx])
                        seen_vlan_ids.add(vlan_ids[idx])
                    net_names = [net['name'] for net in self.networks
                                 if net['id'] in duplicate_net_ids]

                    err_msg = u"Node {0}, interface {1}: {2} networks use " \
                        u"the same VLAN tags. Different VLAN tags should be " \
                        u"assigned to the networks on the same interface.".\
                        format(node_name, if_name, ", ".join(net_names))
                    raise errors.NetworkCheckError(err_msg)

    def check_network_template(self):
        """Check for network template node roles consistency

        If network template is uploaded for cluster it should contain all
        required templates for assigned network roles in each node group
        """
        template = self.cluster.network_config.configuration_template
        # By default network template is None
        if not template:
            return
        assigned_roles = objects.Cluster.get_assigned_roles(self.cluster)
        default_ng_template = template['adv_net_template']['default']

        for role in assigned_roles:
            node_groups = objects.Cluster.get_node_groups(self.cluster, [role])
            for node_group in node_groups:
                # if node group name is not listed in network template,
                # template for 'default' is in use.
                if role not in template['adv_net_template']\
                        .get(node_group.name, default_ng_template)\
                        .get('templates_for_node_role', {}):

                    self.err_msgs.append(
                        "Node role '{0}' is assigned for some nodes in node "
                        "group '{1}', but not found in network template for "
                        "this node group".format(role, node_group.name))
                    self.result.append({"ids": [],
                                        "errors": []})
        self.expose_error_messages()

    def check_configuration(self):
        """check network configuration parameters"""
        if self.net_provider == consts.CLUSTER_NET_PROVIDERS.neutron:
            self.neutron_check_network_address_spaces_intersection()
            self.neutron_check_segmentation_ids()
            self.neutron_check_l3_addresses_not_match_subnet_and_broadcast()
            self.neutron_check_gateways()
        else:
            self.check_public_floating_ranges_intersection()
            self.check_network_address_spaces_intersection()
            self.check_networks_amount()
            self.check_vlan_ids_range_and_intersection()
        self.check_network_classes_exclude_loopback()
        self.check_network_addresses_not_match_subnet_and_broadcast()
        self.check_dns_servers_ips()
        self.check_calculated_network_cidr()

    def check_interface_mapping(self):
        """check mapping of networks to NICs"""
        self.check_untagged_intersection()
        self.check_bond_slaves_speeds()
        self.check_vlan_ids_intersection()
        return self.err_msgs
