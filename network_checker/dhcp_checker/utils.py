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
import functools
import re
import subprocess
import sys

from scapy import all as scapy


DHCP_OFFER_COLUMNS = ('iface', 'mac', 'server_ip', 'server_id', 'gateway',
                      'dport', 'message', 'yiaddr')


def command_util(*command):
    """object with stderr and stdout
    """
    return subprocess.Popen(command, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)


def _check_vconfig():
    """Check vconfig installed or not
    """
    return not command_util('which', 'vconfig').stderr.read()


def _iface_state(iface):
    """For a given iface return it's state
    returns UP, DOWN, UNKNOWN
    """
    state = command_util('ip', 'link', 'show', iface).stdout.read()
    search_result = re.search(r'.*<(?P<state>.*)>.*', state)
    if search_result:
        state_list = search_result.groupdict().get('state', [])
        if 'UP' in state_list:
            return 'UP'
        else:
            return 'DOWN'
    return 'UNKNOWN'


def check_network_up(iface):
    return _iface_state(iface) == 'UP'


def check_iface_exist(iface):
    """Check provided interface exists
    """
    return not command_util("ip", "link", "show", iface).stderr.read()


def filtered_ifaces(ifaces):
    for iface in ifaces:
        if not check_iface_exist(iface):
            sys.stderr.write('Iface {0} does not exist.'.format(iface))
        else:
            if not check_network_up(iface):
                sys.stderr.write('Network for iface {0} is down.'.format(
                    iface))
            else:
                yield iface


def pick_ip(range_start, range_end):
    """Given start_range, end_range generate list of ips
    >>> next(pick_ip('192.168.1.10','192.168.1.13'))
    '192.168.1.10'
    """
    split_address = lambda ip_address: \
        [int(item) for item in ip_address.split('.')]
    range_start = split_address(range_start)
    range_end = split_address(range_end)
    i = 0
    # ipv4 subnet cant be longer that 4 items
    while i < 4:
        # 255 - end of subnet
        if not range_start[i] == range_end[i] and range_start[i] < 255:
            yield '.'.join([str(item) for item in range_start])
            range_start[i] += 1
        else:
            i += 1


def format_options(options):
    """Util for serializing dhcp options
    @options = [1,2,3]
    >>> format_options([1, 2, 3])
    '\x01\x02\x03'
    """
    return "".join((chr(item) for item in options))


def _dhcp_options(dhcp_options):
    """Dhcp options returned by scapy is not in usable format
    [('message-type', 2), ('server_id', '192.168.0.5'),
        ('name_server', '192.168.0.1', '192.168.0.2'), 'end']
    """
    for option in dhcp_options:
        if isinstance(option, (tuple, list)):
            header = option[0]
            if len(option[1:]) > 1:
                yield (header, option)
            else:
                yield (header, option[1])


def format_answer(ans, iface):
    dhcp_options = dict(_dhcp_options(ans[scapy.DHCP].options))
    results = (
        iface, ans[scapy.Ether].src, ans[scapy.IP].src,
        dhcp_options['server_id'], ans[scapy.BOOTP].giaddr,
        ans[scapy.UDP].sport,
        scapy.DHCPTypes[dhcp_options['message-type']],
        ans[scapy.BOOTP].yiaddr)
    return dict(zip(DHCP_OFFER_COLUMNS, results))


def single_format(func):
    """Manage format of dhcp response
    """
    @functools.wraps(func)
    def formatter(*args, **kwargs):
        iface = args[0]
        ans = func(*args, **kwargs)
        #scapy stores all sequence of requests
        #so ans[0][1] would be response to first request
        return [format_answer(response[1], iface) for response in ans]
    return formatter


def multiproc_map(func):
    # multiproc map could not work with format *args
    @functools.wraps(func)
    def workaround(*args, **kwargs):
        args = args[0] if isinstance(args[0], (tuple, list)) else args
        return func(*args, **kwargs)
    return workaround


def filter_duplicated_results(func):
    # due to network infra on broadcast multiple duplicated results
    # returned. This helper filter them out
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        resp = func(*args, **kwargs)
        return (dict(t) for t in set([tuple(d.items()) for d in resp]))
    return wrapper


class VlansContext(object):
    """Contains all logic to manage vlans
    """

    def __init__(self, config):
        """Initialize VlansContext
        @config - list or tuple of (iface, vlan) pairs
        """
        self.config = config

    def __enter__(self):
        for iface, vlans in self.config.iteritems():
            vifaces = []
            for vlan in vlans:
                if vlan > 0:
                    vifaces.append('{0}.{1}'.format(iface, vlan))
            yield str(iface), vifaces

    def __exit__(self, type, value, trace):
        pass


class IfaceState(object):
    """Context manager to control state of iface when dhcp checker is running
    """

    def __init__(self, iface, rollback=True, retry=3):
        self.rollback = rollback
        self.retry = retry
        self.iface = iface
        self.pre_iface_state = _iface_state(iface)
        self.iface_state = self.pre_iface_state
        self.post_iface_state = ''

    def iface_up(self):
        while self.retry and self.iface_state != 'UP':
            command_util('ifconfig', self.iface, 'up')
            self.iface_state = _iface_state(self.iface)
            self.retry -= 1
        if self.iface_state != 'UP':
            raise EnvironmentError(
                'Tried my best to ifup iface {0}.'.format(self.iface))

    def __enter__(self):
        self.iface_up()
        return self.iface

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.pre_iface_state != 'UP' and self.rollback:
            command_util('ifconfig', self.iface, 'down')
        self.post_iface_state = _iface_state(self.iface)
