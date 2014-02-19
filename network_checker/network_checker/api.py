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


from stevedore import driver

from network_checker import config
from network_checker import daemon
from network_checker import xmlrpc


class Api(object):

    namespace = 'network_checker'

    def __init__(self, verification, **kwargs):
        self.verification = verification
        self.server_config = config.get_config()[verification]
        self.verification_config = dict(self.server_config['defaults'],
                                        **kwargs)

    def serve(self):
        daemon.cleanup(self.server_config)
        self.manager = driver.DriverManager(
            self.namespace,
            self.verification,
            invoke_on_load=True,
            invoke_kwds=self.verification_config)
        self.driver = self.manager.driver
        rpc_server = xmlrpc.get_server(self.server_config)
        #TODO(dshulyak) verification api should know what methods to serve
        rpc_server.register_function(self.driver.listen, 'listen')
        rpc_server.register_function(self.driver.send, 'send')
        rpc_server.register_function(self.driver.get_info, 'get_info')
        rpc_server.register_function(self.driver.test, 'test')
        return daemon.run_server(rpc_server, self.server_config)

    def listen(self):
        return xmlrpc.get_client(self.server_config).listen()

    def send(self):
        return xmlrpc.get_client(self.server_config).send()

    def info(self):
        return xmlrpc.get_client(self.server_config).get_info()

    def clean(self):
        return daemon.cleanup(self.server_config)

    def test(self):
        return xmlrpc.get_client(self.server_config).test()
