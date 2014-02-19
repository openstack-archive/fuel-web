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

import threading
import logging
import struct
import socket


LOG = logging.getLogger(__name__)


def _send_packets(group, port, ttl, data, repeat=1):
    ttl_data = struct.pack('@i', ttl)
    _socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    _socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl_data)

    for _ in xrange(repeat):
        _socket.sendto(data, (group, port))


def _register_receiver(group, port, ttl):
    _socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    _socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _socket.bind(('', port))

    group_packed = socket.inet_pton(socket.AF_INET, group)
    group_data = group_packed + struct.pack('=I', socket.INADDR_ANY)
    _socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, group_data)

    return _socket


def _poll_receiver(receiver, messages):
    while True:
        messages.append(receiver.recv(4096))


def multicast(group, port, node_id, ttl=1, timeout=1):
    """Main api for invoking multicast check

    :param group: valid IPv4 multicast group
    :type group: str
    :type port: str
    :param timeout: time it will receives packages
    :param node_id: unique identificator for node
    :type node_id: str

    1. Spawn receivers for provided group
    2. Send traffic to group with specified port
    Must include node_id
    3. Poll listeners
    4. Return received info in format:
    (node_id: [<nodes_ids>,...])
    """
    LOG.info('Starting multicast check '
             '{group}:{port} for node: {node_id}'.format(**locals()))
    try:
        receiver = _register_receiver(group, port, ttl)
    except:
        LOG.exception('Unable to start receivers for {0}'.format(node_id))
        raise
    _send_packets(group, port, ttl, node_id)

    receiver.settimeout(timeout)
    messages = []
    thread = threading.Thread(target=_poll_receiver, args=(receiver, messages))
    thread.daemon = True
    thread.start()
    thread.join(timeout)
    LOG.info('Multicast check is finished for node: {node} with results: '
             '{messages}'.format(node=node_id, messages=messages))
    receiver.close()
    return node_id, messages


if __name__ == '__main__':
    group = '225.0.0.250'
    port = 8123
    node_id = '111'
    ttl = 1

    print multicast(group, port, node_id, ttl)
