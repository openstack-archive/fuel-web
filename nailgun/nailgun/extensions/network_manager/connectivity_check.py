# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

import collections
import six

from nailgun import consts
from nailgun.logger import logger
from nailgun import objects


def check_received_data(cached, received):
    """Check data received from net_probe (received)

    Received data is checked against data from task (cached) for one node.
    Assemble connectivity errors description and return it to the caller.

    :param   cached: data for one node from task.cache
    :type    cached: dict
    :param received: data for one node from net_checker response ('nodes')
    :type  received: dict
    :returns: connectivity errors description (list of dicts - one dict
              per error)
    """
    # Convert cached and received data from interface:vlans form
    # to vlan:interfaces form to perform analysis of interfaces within bonds.

    def build_vlan_ifaces_mapping(networks):
        vlan_ifaces_map = collections.defaultdict(list)

        for net in networks:
            for vlan in net['vlans']:
                vlan_ifaces_map[vlan].append(net['iface'])

        return vlan_ifaces_map

    cached_vlans = build_vlan_ifaces_mapping(cached['networks'])
    received_vlans = build_vlan_ifaces_mapping(received.get('networks', []))

    absent = collections.defaultdict(list)
    for vlan in cached_vlans:
        absent_ifaces = set(cached_vlans[vlan])
        if vlan in received_vlans:
            absent_ifaces -= set(received_vlans[vlan])
            if absent_ifaces and \
                    cached['status'] != consts.NODE_STATUSES.ready and \
                    cached.get('bonds'):

                # We pass NICs instead of bonds while node is not deployed.
                # Check that at least one slave NIC of every bond has received
                # test data.
                for bond_name, slave_names in six.iteritems(cached['bonds']):
                    slaves = set(slave_names)
                    if absent_ifaces >= slaves:
                        # No NIC of this bond has received test data.
                        absent_ifaces.add(bond_name)
                    # These NICs should be excluded as we add bond's name
                    # if no data was received on any of them. If some data
                    # was received on some of them we don't need them
                    # either as the bond passes the test in this case.
                    absent_ifaces -= slaves
                # No bonds' slaves left in absent_ifaces just NICs and bonds.

        # Convert back to interface:vlans form to provide compatibility
        # with current UI. Will be removed when UI is updated.
        for iface in absent_ifaces:
            absent[iface].append(vlan)

    errors = []
    if absent:
        node_db = objects.Node.get_by_mac_or_uid(
            node_uid=cached['uid'])
        for iface in absent:
            error = {
                'uid': cached['uid'],
                'interface': iface,
                'absent_vlans': absent[iface],
                'name': cached['name'],
            }
            if node_db:
                for if_db in node_db.interfaces:
                    if if_db.name == iface:
                        error['mac'] = if_db.mac
                        break
            if 'mac' not in error:
                logger.warning(
                    "verify_networks_resp: can't find "
                    "interface %r for node %r in DB",
                    iface, cached['name']
                )
                error['mac'] = 'unknown'
            errors.append(error)

    return errors


def append_message(original, appendix):
    """Append message to output string with a delimiter

    No delimiter is added if any of strings is empty.
    """
    return '\n'.join(filter(None, (original, appendix)))
