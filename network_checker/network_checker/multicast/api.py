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
import threading
import time

from network_checker import consts

LOG = logging.getLogger(__name__)


class MulticastChecker(object):

    name = 'fuel_multicast'

    def __init__(self, group=None, port=None, uid=None, iface='eth0',
                 ttl=1, repeat=1, timeout=10):
        self.group = group
        self.port = port
        self.ttl = ttl
        self.node_id = uid
        self.repeat = repeat
        self.timeout = timeout
        self.receiver = None
        self.messages = []
        self.iface = iface

    def send(self):
        ttl_data = struct.pack('@i', self.ttl)
        _socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL,
                           ttl_data)
        _socket.setsockopt(socket.SOL_SOCKET, 25, self.iface)

        for _ in xrange(self.repeat):
            _socket.sendto(self.node_id, (self.group, self.port))
        return consts.READY

    def listen(self):
        self.receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.receiver.bind(('', self.port))

        group_packed = socket.inet_pton(socket.AF_INET, self.group)
        group_data = group_packed + struct.pack('=I', socket.INADDR_ANY)
        self.receiver.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                                 group_data)
        # 25 - SO_BINDTODEVICE
        self.receiver.setsockopt(socket.SOL_SOCKET, 25, self.iface)
        self.thread = threading.Thread(target=self._poll_receiver)
        self.thread.daemon = True
        self.thread.start()
        return consts.READY

    def _poll_receiver(self):
        while True:
            self.messages.append(self.receiver.recv(1024))
            time.sleep(0.2)

    def _close_receiver(self):
        self.receiver.close()

    def get_info(self):
        self.thread.join(self.timeout)
        self._close_receiver()
        return self.messages
