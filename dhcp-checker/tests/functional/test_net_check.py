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

import os
import unittest

from multiprocessing import Process
import socket
import json
import time
import signal
from net_check import api
from scapy import all as scapy
import pcap


class TestNetCheckListener(unittest.TestCase):

    def setUp(self):
        directory_path = os.path.dirname(__file__)
        self.scapy_data = scapy.rdpcap(os.path.join(directory_path,
                                                    'vlan.pcap'))
        self.config = {
            "src": "1.0.0.0", "ready_port": 31338,
            "ready_address": "localhost", "dst": "1.0.0.0",
            "interfaces": {"eth0": "0,100,100,101,102,103,104,105,106,107"},
            "action": "listen",
            "cookie": "Nailgun:", "dport": 31337, "sport": 31337,
            "src_mac": None, "dump_file": "/var/tmp/net-probe-dump"
        }
        self.start_socket()
        listener = api.Listener(self.config)
        self.listener = Process(target=listener.run)
        self.listener.start()

    def start_socket(self):
        self.ready_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ready_socket.bind((self.config['ready_address'],
                                self.config['ready_port']))
        self.ready_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.ready_socket.listen(1)

    def send_packets(self):
        for p in self.scapy_data:
            scapy.sendp(p, iface='eth0')

    def test_listener(self):
        connection, address = self.ready_socket.accept()
        request = connection.recv(1024)
        self.assertEqual('READY', request.decode())
        connection.close()
        self.ready_socket.shutdown(socket.SHUT_RDWR)
        self.ready_socket.close()

        self.send_packets()
        time.sleep(10)
        os.kill(self.listener.pid, signal.SIGINT)
        time.sleep(10)
        with open(self.config['dump_file'], 'r') as f:
            data = json.loads(f.read())

        self.assertEqual(data,
            {u'eth0': {
                u'102': {u'1': [u'eth0'], u'2': [u'eth0']},
                u'103': {u'1': [u'eth0'], u'2': [u'eth0']},
                u'100': {u'1': [u'eth0'], u'2': [u'eth0']},
                u'101': {u'1': [u'eth0'], u'2': [u'eth0']},
                u'106': {u'1': [u'eth0'], u'2': [u'eth0']},
                u'107': {u'1': [u'eth0'], u'2': [u'eth0']},
                u'104': {u'1': [u'eth0'], u'2': [u'eth0']},
                u'105': {u'1': [u'eth0'], u'2': [u'eth0']}}})

    def tearDown(self):
        self.ready_socket.close()
        self.listener.terminate()


class TestNetCheckSender(unittest.TestCase):

    def setUp(self):
        directory_path = os.path.dirname(__file__)
        self.scapy_data = scapy.rdpcap(os.path.join(directory_path,
                                                    'vlan.pcap'))
        self.config = {
            "src": "1.0.0.0", "ready_port": 31338,
            "ready_address": "localhost", "dst": "1.0.0.0",
            "interfaces": {"eth0": "0,100,100,101,102,103,104,105,106,107"},
            "action": "listen",
            "cookie": "Nailgun:", "dport": 31337, "sport": 31337,
            "src_mac": None,
            "dump_file": "/var/tmp/net-probe-dump",
            "uid": "2"
        }

    def start_pcap_listener(self):
        self.pcap_listener = pcap.pcap('eth0')
        filter_string = 'udp and dst port {0}'.format(self.config['dport'])
        self.pcap_listener.setfilter(filter_string)

    def start_sender(self):
        sender = api.Sender(self.config)
        self.sender = Process(target=sender.run)
        self.sender.start()

    def test_sender(self):
        self.start_pcap_listener()
        self.start_sender()
        time.sleep(10)
        self.sender.join()
        self.assertEqual(self.pcap_listener.stats()[0], 50)

        packet = self.pcap_listener.next()

        ether = scapy.Ether(packet[1])

        self.assertEqual(ether[scapy.UDP].sport, self.config['sport'])
        self.assertEqual(ether[scapy.UDP].dport, self.config['dport'])
