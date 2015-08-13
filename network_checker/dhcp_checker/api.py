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

import itertools
import logging
import time

from scapy import config as scapy_config

scapy_config.use_pcap = True

logging.getLogger('scapy.runtime').setLevel(logging.CRITICAL)

from dhcp_checker import utils
import pcap
from scapy import all as scapy

LOG = logging.getLogger(__name__)


def _get_dhcp_discover_message(iface):

    dhcp_options = [("message-type", "discover"),
                    ("param_req_list", utils.format_options(
                        [1, 2, 3, 4, 5, 6,
                         11, 12, 13, 15, 16, 17, 18, 22, 23,
                         28, 40, 41, 42, 43, 50, 51, 54, 58, 59, 60, 66, 67])),
                    "end"]

    fam, hw = scapy.get_if_raw_hwaddr(iface)

    dhcp_discover = (
        scapy.Ether(src=hw, dst="ff:ff:ff:ff:ff:ff") /
        scapy.IP(src="0.0.0.0", dst="255.255.255.255") /
        scapy.UDP(sport=68, dport=67) /
        scapy.BOOTP(chaddr=hw) /
        scapy.DHCP(options=dhcp_options))

    return dhcp_discover


@utils.single_format
def check_dhcp_on_eth(iface, timeout):
    """Check if there is roque dhcp server in network on given iface
        @iface - name of the ethernet interface
        @timeout - scapy timeout for waiting on response
    >>> check_dhcp_on_eth('eth1')
    """
    scapy.conf.iface = iface
    scapy.conf.checkIPaddr = False
    dhcp_discover = _get_dhcp_discover_message(iface)
    ans, unans = scapy.srp(dhcp_discover, multi=True,
                           nofilter=1, timeout=timeout, verbose=0)

    return ans


def check_dhcp(ifaces, timeout=5, repeat=2):
    """Given list of ifaces. Process them in separate processes
    @ifaces - lsit of ifaces
    @timeout - timeout for scapy to wait for response
    @repeat - number of packets sended
    >>> check_dhcp(['eth1', 'eth2'])
    """
    config = {}
    for iface in ifaces:
        config[iface] = ()
    return check_dhcp_with_vlans(config, timeout=timeout, repeat=repeat)


def send_dhcp_discover(iface):
    dhcp_discover = _get_dhcp_discover_message(iface)
    scapy.sendp(dhcp_discover, iface=iface, verbose=0)


def make_listeners(ifaces):
    listeners = []
    for iface in ifaces:
        try:
            listener = pcap.pcap(iface)
            mac_filter = utils.create_mac_filter(iface)
            # catch the answers only for this iface
            listener.setfilter('((dst port 68) and {0})'.format(mac_filter))
            listeners.append(listener)
        except Exception:
            LOG.warning(
                'Spawning listener for {iface} failed.'.format(iface=iface))
    return listeners


@utils.filter_duplicated_results
def check_dhcp_with_vlans(config, timeout=5, repeat=2):
    """Provide config of {iface: [vlans..]} pairs
    @config - {'eth0': (100, 101), 'eth1': (100, 102)}
    """
    # vifaces - list of pairs ('eth0', ['eth0.100', 'eth0.101'])
    with utils.VlansContext(config) as vifaces:
        ifaces, vlans = zip(*vifaces)
        listeners = make_listeners(ifaces)

        for _ in xrange(repeat):
            for i in utils.filtered_ifaces(itertools.chain(ifaces, *vlans)):
                send_dhcp_discover(i)
            time.sleep(timeout)

        for l in listeners:
            for pkt in l.readpkts():
                yield utils.format_answer(scapy.Ether(pkt[1]), l.name)


@utils.single_format
def check_dhcp_request(iface, server, range_start, range_end, timeout=5):
    """Provide interface, server endpoint and pool of ip adresses
        Should be used after offer received
        >>> check_dhcp_request('eth1','10.10.0.5','10.10.0.10','10.10.0.15')
    """

    scapy.conf.iface = iface

    scapy.conf.checkIPaddr = False

    fam, hw = scapy.get_if_raw_hwaddr(iface)

    ip_address = next(utils.pick_ip(range_start, range_end))

    # note lxc dhcp server does not respond to unicast
    dhcp_request = (scapy.Ether(src=hw, dst="ff:ff:ff:ff:ff:ff") /
                    scapy.IP(src="0.0.0.0", dst="255.255.255.255") /
                    scapy.UDP(sport=68, dport=67) /
                    scapy.BOOTP(chaddr=hw) /
                    scapy.DHCP(options=[("message-type", "request"),
                                        ("server_id", server),
                                        ("requested_addr", ip_address),
                                        "end"]))
    ans, unans = scapy.srp(dhcp_request, nofilter=1, multi=True,
                           timeout=timeout, verbose=0)
    return ans
