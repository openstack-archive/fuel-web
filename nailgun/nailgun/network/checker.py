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
from itertools import product

import netaddr

from nailgun.api.models import NetworkGroup
from nailgun.api.serializers.network_configuration \
    import NetworkConfigurationSerializer
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.task.helpers import TaskHelper


def calc_cidr_from_gw_mask(net_group):
    try:
        return netaddr.IPNetwork(net_group['gateway'] + '/' +
                                 net_group['netmask']).cidr
    except (netaddr.AddrFormatError, KeyError):
        return None


class NetworkCheck(object):

    def __init__(self, task, data):
        """Collect Network Groups data
        """
        self.cluster = task.cluster
        self.task = task
        self.data = data
        self.net_man = self.cluster.network_manager()
        self.net_provider = self.cluster.net_provider
        admin_ng = self.net_man.get_admin_network_group()
        fields = NetworkGroup.__mapper__.columns.keys()
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
        if 'networks' in data:
            for data_net in data['networks']:
                for net in self.networks:
                    if data_net['id'] == net['id']:
                        net.update(data_net)
                        break
                else:
                    raise errors.NetworkCheckError(
                        u"Invalid network ID: {0}".format(data_net['id']),
                        add_client=False)

        self.result = []
        self.err_msgs = []

    def expose_error_messages(self):
        TaskHelper.expose_network_check_error_messages(
            self.task,
            self.result,
            self.err_msgs)

    def check_untagged_intersection(self):
        # check if there are untagged networks on the same interface
        untagged_nets = set([n['name'] for n in self.networks
                             if n['vlan_start'] is None])
        # check only if we have 2 or more untagged networks
        pub_flt = set(['public', 'floating'])
        if len(untagged_nets) >= 2 and untagged_nets != pub_flt:
            logger.info(
                "Untagged networks found, "
                "checking intersection between them...")
            interfaces = []
            for node in self.cluster.nodes:
                for iface in node.interfaces:
                    interfaces.append(iface)
            found_intersection = []

            for iface in interfaces:
                # network name is changed for Admin on UI
                nets = [[ng['name'] for ng in self.networks
                         if n.id == ng['id']][0]
                        for n in iface.assigned_networks]
                crossed_nets = set(nets) & untagged_nets
                if len(crossed_nets) > 1 and crossed_nets != pub_flt:
                    err_net_names = ['"{0}"'.format(i)
                                     for i in crossed_nets]
                    found_intersection.append(
                        [iface.node.name, err_net_names])

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
                self.result.append({"id": [],
                                    "range_errors": [],
                                    "errors": ["untagged"]})
        self.expose_error_messages()

    def check_net_addr_spaces_intersection(self, pub_cidr):
        # check intersection of networks address spaces
        # for all networks
        def addr_space(ng, ng_pair):
            if ng['name'] == 'floating':
                return [netaddr.IPRange(v[0], v[1])
                        for v in ng['ip_ranges']]
            elif ng['name'] == 'public':
                if ng_pair['name'] == 'floating':
                    return [netaddr.IPRange(v[0], v[1])
                            for v in ng['ip_ranges']]
                else:
                    return [pub_cidr]
            else:
                return [netaddr.IPNetwork(ng['cidr'])]

        for ngs in combinations(self.networks, 2):
            for addrs in product(addr_space(ngs[0], ngs[1]),
                                 addr_space(ngs[1], ngs[0])):
                if self.net_man.is_range_intersection(addrs[0], addrs[1]):
                    self.err_msgs.append(
                        u"Address space intersection between "
                        "networks: {0}.".format(
                            ", ".join([ngs[0]['name'], ngs[1]['name']])
                        )
                    )
                    self.result.append({
                        "id": [int(ngs[0]["id"]), int(ngs[1]["id"])],
                        "range_errors": [str(addrs[0]), str(addrs[1])],
                        "errors": ["cidr"]
                    })
        self.expose_error_messages()

    def check_public_floating_ranges_intersection(self):
        # 1. Check intersection of networks address spaces inside
        #    Public and Floating network
        # 2. Check that Public Gateway is in Public CIDR
        # 3. Check that Public IP ranges are in Public CIDR
        ng = [ng for ng in self.networks
              if ng['name'] == 'public'][0]
        pub_gw = netaddr.IPAddress(ng['gateway'])
        pub_cidr = calc_cidr_from_gw_mask(ng)
        if not pub_cidr:
            self.err_msgs.append(
                u"Invalid gateway or netmask for public network")
            self.result.append({"id": int(ng["id"]),
                                "range_errors": [],
                                "errors": ["netmask"]})
            self.expose_error_messages()
        # Check intersection of networks address spaces inside
        # Public and Floating network
        for ng in self.networks:
            if ng['name'] in ['public', 'floating']:
                nets = [netaddr.IPRange(v[0], v[1])
                        for v in ng['ip_ranges']]
                for npair in combinations(nets, 2):
                    if self.net_man.is_range_intersection(npair[0], npair[1]):
                        self.err_msgs.append(
                            u"Address space intersection between ranges "
                            "of {0} network.".format(ng['name'])
                        )
                        self.result.append({"id": int(ng["id"]),
                                            "range_errors": [],
                                            "errors": ["range"]})
                    if pub_gw in npair[0] or pub_gw in npair[1]:
                        self.err_msgs.append(
                            u"Address intersection between "
                            u"public gateway and IP range "
                            u"of {0} network.".format(ng['name'])
                        )
                        self.result.append({"id": int(ng["id"]),
                                            "range_errors": [],
                                            "errors": ["gateway"]})
                # Check that Public IP ranges are in Public CIDR
                if ng['name'] == 'public':
                    for net in nets:
                        if net not in pub_cidr:
                            self.err_msgs.append(
                                u"Public gateway or public ranges "
                                u"are not in one CIDR."
                            )
                            self.result.append({"id": int(ng["id"]),
                                                "range_errors": [],
                                                "errors": ["range"]})
        self.expose_error_messages()
        return pub_cidr

    def neutron_check_segmentation_ids(self):
        # check: networks VLAN IDs should not be in
        # Neutron L2 private VLAN ID range (VLAN segmentation only)
        tagged_nets = dict((n["name"], n["vlan_start"]) for n in filter(
            lambda n: (n["vlan_start"] is not None), self.networks))

        if tagged_nets:
            if self.task.cluster.net_segment_type == 'vlan':
                if 'neutron_parameters' in self.data:
                    l2cfg = self.data['neutron_parameters']['L2']
                else:
                    l2cfg = self.task.cluster.neutron_config.L2
                for net, net_conf in l2cfg['phys_nets'].iteritems():
                    vrange = net_conf['vlan_range']
                    if vrange:
                        break
                else:
                    err_msg = u"Wrong VLAN range for Neutron L2.\n"
                    raise errors.NetworkCheckError(err_msg, add_client=False)

                net_intersect = [name for name, vlan in tagged_nets.iteritems()
                                 if vrange[0] <= vlan <= vrange[1]]
                if net_intersect:
                    nets_with_errors = ", ". \
                        join(net_intersect)
                    err_msg = u"Networks VLAN tags are in " \
                              u"ID range defined for Neutron L2. " \
                              u"You should assign VLAN tags that are " \
                              u"not in Neutron L2 VLAN ID range:\n{0}". \
                        format(nets_with_errors)
                    raise errors.NetworkCheckError(err_msg, add_client=False)

            # check: networks VLAN IDs should not intersect
            net_intersect = [name for name, vlan in tagged_nets.iteritems()
                             if tagged_nets.values().count(vlan) >= 2]
            if net_intersect:
                err_msg = u"{0} networks use the same VLAN tags. " \
                          u"You should assign different VLAN tag " \
                          u"to every network.".format(", ".join(net_intersect))
                raise errors.NetworkCheckError(err_msg, add_client=False)

    def neutron_check_network_group_sizes(self):
        # check network groups sizes
        for ng in self.networks:
            # network_size is calculated in case of public
            if ng['name'] not in ('private', 'public'):
                # ng['amount'] is always equal 1 for Neutron
                if netaddr.IPNetwork(ng['cidr']).size < ng['network_size']:
                    self.err_msgs.append(
                        u"CIDR size for network '{0}' "
                        u"is less than required".format(ng['name'])
                    )
                    self.result.append({
                        "id": int(ng["id"]),
                        "range_errors": [],
                        "errors": ["size"]
                    })
        self.expose_error_messages()

    def neutron_check_network_address_spaces_intersection(self):
        # calculate and check public CIDR
        public = filter(lambda ng: ng['name'] == 'public', self.networks)[0]
        public_cidr = calc_cidr_from_gw_mask(public)
        if not public_cidr:
            self.err_msgs.append(
                u"Invalid gateway or netmask for public network")
            self.result.append({"id": int(public["id"]),
                                "range_errors": [],
                                "errors": ["netmask"]})
            self.expose_error_messages()
        public['cidr'] = str(public_cidr)

        net_errors = []
        # check intersection of address ranges
        # between all networks
        for ngs in combinations(self.networks, 2):
            net_errors = []
            if ngs[0].get('cidr') and ngs[1].get('cidr'):
                cidr1 = netaddr.IPNetwork(ngs[0]['cidr'])
                cidr2 = netaddr.IPNetwork(ngs[1]['cidr'])
                if self.net_man.is_cidr_intersection(cidr1, cidr2):
                    net_errors.append("cidr")
                    self.err_msgs.append(
                        u"Intersection between network address "
                        u"spaces found:\n{0}".format(
                            ", ".join([ngs[0]['name'], ngs[1]['name']])
                        )
                    )
            if net_errors:
                self.result.append({
                    "id": [int(ngs[0]["id"]), int(ngs[1]["id"])],
                    "errors": net_errors
                })
        self.expose_error_messages()

        # check Floating Start and Stop IPs belong to Public CIDR
        if 'neutron_parameters' in self.data:
            pre_net = self.data['neutron_parameters']['predefined_networks']
        else:
            pre_net = self.task.cluster.neutron_config.predefined_networks
        fl_range = pre_net['net04_ext']['L3']['floating']
        fl_ip_range = netaddr.IPRange(fl_range[0], fl_range[1])
        if fl_ip_range not in public_cidr:
            net_errors.append("float_range")
            self.err_msgs.append(
                u"Floating address range {0}:{1} is not in public "
                u"address space {2}.".format(
                    netaddr.IPAddress(fl_range[0]),
                    netaddr.IPAddress(fl_range[1]),
                    public['cidr']
                )
            )
            self.result = [{"id": int(public["id"]), "errors": net_errors}]
        self.expose_error_messages()

        # Check intersection of networks address spaces inside
        # Public network
        ranges = [netaddr.IPRange(v[0], v[1])
                  for v in public['ip_ranges']] + [fl_ip_range]
        public_gw = netaddr.IPAddress(public['gateway'])
        for npair in combinations(ranges, 2):
            if self.net_man.is_range_intersection(npair[0], npair[1]):
                if fl_ip_range in npair:
                    self.err_msgs.append(
                        u"Address space intersection between ranges "
                        u"of public and external network."
                    )
                else:
                    self.err_msgs.append(
                        u"Address space intersection between ranges "
                        u"of public network."
                    )
                self.result.append({"id": int(public["id"]),
                                    "range_errors": [],
                                    "errors": ["range"]})
            if public_gw in npair[0] or public_gw in npair[1]:
                self.err_msgs.append(
                    u"Address intersection between public gateway "
                    u"and IP range of public network."
                )
                self.result.append({"id": int(public["id"]),
                                    "range_errors": [],
                                    "errors": ["gateway"]})
        self.expose_error_messages()

        # Check that Public IP ranges are in Public CIDR
        for net in ranges:
            if net not in public_cidr:
                self.err_msgs.append(
                    u"Public gateway or public ranges "
                    u"are not in one CIDR."
                )
                self.result.append({"id": int(public["id"]),
                                    "range_errors": [],
                                    "errors": ["range"]})
        self.expose_error_messages()

        # check internal Gateway is in Internal CIDR
        internal = pre_net['net04']['L3']
        if internal.get('cidr') and internal.get('gateway'):
            cidr = netaddr.IPNetwork(internal['cidr'])
            if netaddr.IPAddress(internal['gateway']) not in cidr:
                net_errors.append("gateway")
                self.err_msgs.append(
                    u"Internal gateway {0} is not in internal "
                    u"address space {1}.".format(
                        internal['gateway'], internal['cidr']
                    )
                )
            if self.net_man.is_range_intersection(fl_ip_range, cidr):
                net_errors.append("cidr")
                self.err_msgs.append(
                    u"Intersection between internal CIDR and floating range."
                )
        else:
            net_errors.append("format")
            self.err_msgs.append(
                u"Internal gateway or CIDR specification is invalid."
            )
        if net_errors:
            self.result.append({"id": None,
                                "name": "internal",
                                "errors": net_errors})
        self.expose_error_messages()

    def neutron_check_interface_mapping(self):

        # check if there any networks
        # on the same interface as admin network (main)
        admin_interfaces = map(lambda node: node.admin_interface,
                               self.cluster.nodes)
        found_intersection = []

        all_roles = set([n["id"] for n in self.networks
                         if n != self.networks[0]])
        for iface in admin_interfaces:
            nets = dict(
                (n.id, n.name)
                for n in iface.assigned_networks)

            err_nets = set(nets.keys()) & all_roles
            if err_nets:
                err_net_names = [
                    '"{0}"'.format(nets[i]) for i in err_nets]
                found_intersection.append(
                    [iface.node.name, err_net_names])

        if found_intersection:
            nodes_with_errors = [
                u'Node "{0}": {1}'.format(
                    name,
                    ", ".join(_networks)
                ) for name, _networks in found_intersection]
            err_msg = u"Some networks are " \
                      "assigned to the same physical interface as " \
                      "admin (PXE) network. You should move them to " \
                      "another physical interfaces:\n{0}". \
                format("\n".join(nodes_with_errors))
            raise errors.NetworkCheckError(err_msg, add_client=False)

        # check if there any networks
        # on the same interface as private network (for vlan)
        if self.cluster.net_segment_type == 'vlan':
            private_interfaces = []
            # there should be shorter method to do this !
            for node in self.cluster.nodes:
                for iface in node.interfaces:
                    for anet in iface.assigned_networks:
                        if anet.name == 'private':
                            private_interfaces.append(iface)
            found_intersection = []

            all_roles = set(n["id"] for n in self.networks
                            if n["name"] != 'private')
            for iface in private_interfaces:
                nets = dict(
                    (n.id, n.name)
                    for n in iface.assigned_networks)

                err_nets = set(nets.keys()) & all_roles
                if err_nets:
                    err_net_names = [
                        '"{0}"'.format(nets[i]) for i in err_nets]
                    found_intersection.append(
                        [iface.node.name, err_net_names])

            if found_intersection:
                nodes_with_errors = [
                    u'Node "{0}": {1}'.format(
                        name,
                        ", ".join(_networks)
                    ) for name, _networks in found_intersection]
                err_msg = u"Some networks are " \
                          "assigned to the same physical interface as " \
                          "private network. You should move them to " \
                          "another physical interfaces:\n{0}". \
                    format("\n".join(nodes_with_errors))
                raise errors.NetworkCheckError(err_msg, add_client=False)

        # check untagged networks intersection
        untagged_nets = set(
            n["id"] for n in filter(
                lambda n: (n["vlan_start"] is None), self.networks))
        if untagged_nets:
            logger.info(
                "Untagged networks found, "
                "checking intersection between them...")
            interfaces = []
            for node in self.cluster.nodes:
                for iface in node.interfaces:
                    interfaces.append(iface)
            found_intersection = []

            for iface in interfaces:
                nets = dict(
                    (n.id, n.name)
                    for n in iface.assigned_networks)

                crossed_nets = set(nets.keys()) & untagged_nets
                if len(crossed_nets) > 1:
                    err_net_names = [
                        '"{0}"'.format(nets[i]) for i in crossed_nets]
                    found_intersection.append(
                        [iface.node.name, err_net_names])

            if found_intersection:
                nodes_with_errors = [
                    u'Node "{0}": {1}'.format(
                        name,
                        ", ".join(_networks)
                    ) for name, _networks in found_intersection]
                err_msg = u"Some untagged networks are " \
                          "assigned to the same physical interface. " \
                          "You should assign them to " \
                          "different physical interfaces:\n{0}". \
                    format("\n".join(nodes_with_errors))
                raise errors.NetworkCheckError(err_msg, add_client=False)

    def check_configuration(self):
        if self.net_provider == 'neutron':
            self.neutron_check_network_address_spaces_intersection()
            self.neutron_check_segmentation_ids()
            self.neutron_check_network_group_sizes()
        else:
            pub_cidr = self.check_public_floating_ranges_intersection()
            self.check_net_addr_spaces_intersection(pub_cidr)

    def check_interface_mapping(self):
        if self.net_provider == 'neutron':
            self.neutron_check_interface_mapping()
        else:
            self.check_untagged_intersection()
