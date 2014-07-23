#    Copyright 2014 Mirantis, Inc.
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

import logging
import socket
import struct

import pcap
import scapy.all as scapy

LOG = logging.getLogger(__name__)

# it is not defined in every python version
SO_BINDTODEVICE = 25


class MulticastChecker(object):

    def __init__(self, group='225.0.0.250', port='13100',
                 uid='999', ifaces=['eth0'],
                 ttl=1, repeat=1, timeout=3):
        self.group = group
        self.port = int(port)
        self.ttl = ttl
        self.uid = uid
        self.repeat = repeat
        self.timeout = timeout
        self.receivers = []
        self.listeners = []
        self.messages = []
        self.ifaces = ifaces

    def _send_iface(self, iface):
        ttl_data = struct.pack('@i', self.ttl)
        _socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL,
                           ttl_data)
        _socket.setsockopt(
            socket.SOL_SOCKET,
            SO_BINDTODEVICE, iface)

        for _ in xrange(self.repeat):
            _socket.sendto(self.uid, (self.group, self.port))

    def send(self):
        for iface in self.ifaces:
            self._send_iface(iface)
        return {'group': self.group,
                'port': self.port,
                'ifaces': self.ifaces,
                'uid': self.uid}

    def listen(self):
        for iface in self.ifaces:
            self._register_group(iface)
            self._start_listener(iface)
        return {'group': self.group,
                'port': self.port,
                'ifaces': self.ifaces,
                'uid': self.uid}

    def _register_group(self, iface):
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        receiver.setsockopt(
            socket.SOL_SOCKET,
            SO_BINDTODEVICE, iface)
        receiver.bind(('', self.port))
        group_packed = socket.inet_aton(self.group)
        group_data = struct.pack('4sL', group_packed, socket.INADDR_ANY)
        receiver.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                            group_data)
        self.receivers.append(receiver)

    def _start_listener(self, iface):
        listener = pcap.pcap(iface)
        udp_filter = 'udp and dst port {0}'.format(self.port)
        listener.setfilter(udp_filter)
        self.listeners.append(listener)

    def get_info(self):
        for listener in self.listeners:
            for sock, pack in listener.readpkts():
                pack = scapy.Ether(pack)
                data, _ = pack[scapy.UDP].extract_padding(pack[scapy.UDP].load)
                self.messages.append(data.decode())
        for receiver in self.receivers:
            receiver.close()
        return list(set(self.messages))

    def test(self):
        return {'test': 'test'}
