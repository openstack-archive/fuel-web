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


import xmlrpclib
from SimpleXMLRPCServer import SimpleXMLRPCServer


def get_client(config):
    url = 'http://{0}:{1}'.format(config['bind_ip'], config['bind_port'])
    return xmlrpclib.ServerProxy(url)


def get_server(config):
    #TODO server should communicate over unix socket
    return SimpleXMLRPCServer((config['bind_ip'], config['bind_port']))
