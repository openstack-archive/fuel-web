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
  fuel-netcheck multicast listen '{"node_id": "111", "group": "225.0.0.250",
  "port": 8890}'
  fuel-netcheck multicast send '{"node_id": "111", "group": "225.0.0.250",
  "port": 8890}'
  fuel-netcheck multicast get_info '{"node_id": "111", "group": "225.0.0.250",
  "port": 8890}'

Options:
  -h --help     Show this screen.
  --version     Show version.

"""
import json
import multiprocessing
import socket
import sys

from stevedore import driver

from network_checker import consts
from network_checker import mcollective_action
from network_checker import server


class Api(object):

    def __init__(self, check, config):
        self.manager = driver.DriverManager(
            'network_checker', check,
            invoke_on_load=True, invoke_kwds=config)
        self.config = config
        self.checker = self.manager.driver

    def listen(self):
        comm_server = server.CommunicationServer(self.checker)
        comm_server.cleanup()
        comm_server.init_server()
        proc = multiprocessing.Process(target=comm_server.daemonize_serve)
        proc.start()
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect('/tmp/{name}'.format(name=self.checker.name))
        client.send('listen')
        client.settimeout(5)
        return client.recv(1024)

    def send(self):
        return self.checker.send()

    def get_info(self):
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect('/tmp/{name}'.format(name=self.checker.name))
        client.send('get_info')
        data = client.recv(1024)
        return data

    def clean(self):
        comm_server = server.CommunicationServer(self.checker)
        comm_server.cleanup()


def nailgun_uid():
    with open('/etc/nailgun_uid') as f:
        return f.read().strip('\n')


def mcollective():

    with mcollective_action.MCollectiveAction() as mc:
        # in general config should be broadcasted to all nodes and then
        # used by node uid
        node_uid = nailgun_uid()
        config = mc.request['data']['config'][node_uid]
        command = mc.request['data']['command']
        check = mc.request['data']['check']
        api = Api(check, config)
        try:
            result = getattr(api, command)()
            if consts.READY in result:
                mc.reply['status'] = 'inprogress'
            else:
                mc.reply['status'] = 'success'
                result = json.loads(result)
            mc.reply['data'] = result
        except Exception:
            api.clean()
            mc.reply['status'] = 'error'
            raise


def cli():
    # cli is very usefull for debugging purposes
    from docopt import docopt
    arguments = docopt(__doc__, version='Fuel Network Checker 0.1')
    config = json.loads(arguments['<config>'])
    api = Api(arguments['<check>'], config)
    result = getattr(api, arguments['<command>'])()
    print(result)
    sys.exit(0)
