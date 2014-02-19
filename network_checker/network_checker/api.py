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
"""Fuel network checker
<check> should be multicast | dhcp | l2
<command> should be listen | send | get_info
<config> arbitrary set of jsonized parameters specific for each check

Usage:
  fuel-netcheck <check> <command> <config>
  fuel-netcheck (-h | --help)
  fuel-netcheck --version

Examples:
  fuel-netcheck multicast listen
    '{"node_id": 111, "group": "225.0.0.250", "port": 8890}'
  fuel-netcheck multicast send
    '{"node_id": 111, "group": "225.0.0.250", "port": 8890}'
  fuel-netcheck multicast get_info
    '{"node_id": 111, "group": "225.0.0.250", "port": 8890}'

Options:
  -h --help     Show this screen.
  --version     Show version.

"""
import json
import multiprocessing
import socket
import sys

from docopt import docopt
from stevedore import driver

from network_checker import server


class Api(object):

    @classmethod
    def listen(cls, checker):
        comm_server = server.CommunicationServer(checker)
        proc = multiprocessing.Process(target=comm_server.daemonize_serve)
        proc.start()
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect('/tmp/{name}'.format(name=checker.name))
        client.send('listen')
        client.settimeout(5)
        return client.recv(1024)

    @classmethod
    def send(cls, checker):
        return checker.send()

    @classmethod
    def get_info(cls, checker):
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect('/tmp/{name}'.format(name=checker.name))
        client.send('get_info')
        client.settimeout(10)
        data = client.recv(1024)
        return data


def main():
    arguments = docopt(__doc__, version='Fuel Network Checker 0.1')
    config = json.loads(arguments['<config>'])
    manager = driver.DriverManager('network_checker', arguments['<check>'],
                                   invoke_on_load=True, invoke_kwds=config)
    result = getattr(Api, arguments['<command>'])(manager.driver)
    print(result)
    sys.exit(0)
