# -*- coding: utf-8 -*-

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


from fuelclient.tests.base import BaseTestCase


class TestHandlers(BaseTestCase):

    def test_env_action(self):
        #check env help
        env_help = self.run_cli_command(command_line="env --help")
        help_msg = """usage: python-fuelclient [global optional args] environment
       [-h] [-l] [-s] [--delete] [--rel REL] [-c] [--name NAME]
       [-m {multinode,ha}] [-n {nova,neutron}] [--nst {gre,vlan}]

optional arguments:
  -h, --help            show this help message and exit
  -l, --list            List all available environments.
  -s, --set             Set environment parameters (e.g name, deployment mode)
  --delete              Delete environment with specific env or name
  --rel REL, --release REL
                        Release id
  -c, --env-create, --create
                        Create a new environment with specific release id and
                        name.
  --name NAME, --env-name NAME
                        environment name
  -m {multinode,ha}, --mode {multinode,ha}, --deployment-mode {multinode,ha}
                        Set deployment mode for specific environment.
  -n {nova,neutron}, --net {nova,neutron}, --network-mode {nova,neutron}
                        Set network mode for specific environment.
  --nst {gre,vlan}, --net-segment-type {gre,vlan}
                        Set network segment type
"""
        self.assertEqual(env_help.stdout, help_msg)
        #no clusters
        env_call = self.run_cli_command(command_line="env")
        env_message = env_call.stdout.split("\n")
        #no env
        self.assertEqual(env_message[2], '')

        env_set_call = self.run_cli_command(
            command_line="env set", with_erros=True)
        #should not work without env id
        self.assertIn("required", env_set_call.stderr)

        env_create_call = self.run_cli_command(
            command_line="env create", with_erros=True)
        #should not work without env id
        self.assertIn("required", env_create_call.stderr)

        env_delete_call = self.run_cli_command(
            command_line="env delete", with_erros=True)
        #should not work without env id
        self.assertIn("required", env_delete_call.stderr)

        env_create_with_args_call = self.run_cli_command(
            command_line="env create --name=TestEnv --release=1")
        create_env_msg = "Environment 'TestEnv' with id=1, mode=multinode and network-mode=nova_network was created!\n"
        self.assertEqual(env_create_with_args_call.stdout, create_env_msg)

        env_set_name_call = self.run_cli_command(
            command_line="--env-id=1 env set --name=NewEnv")
        set_env_name_msg = "Environment with id=1 was renamed to 'NewEnv'.\n"
        self.assertEqual(env_set_name_call.stdout, set_env_name_msg)

        env_set_net_call = self.run_cli_command(
            command_line="--env-id=1 env set --mode=ha")
        set_env_net_msg = "Mode of environment with id=1 was set to 'ha'.\n"
        self.assertEqual(env_set_net_call.stdout, set_env_net_msg)

    def test_node_action(self):
        help_msg = """usage: python-fuelclient [global optional args] node [-h] [-l] [-s] [--delete]
                                                     [--default] [-d] [-u]
                                                     [--dir DIR]
                                                     [--node NODE [NODE ...]]
                                                     [-r ROLE] [--net]
                                                     [--disk] [-f]

optional arguments:
  -h, --help            show this help message and exit
  -l, --list            List all nodes.
  -s, --set             Set role for specific node.
  --delete              Delete specific node from environment.
  --default             Get default network configuration of some node
  -d, --download        Download configuration of specific node
  -u, --upload          Upload configuration to specific node
  --dir DIR             Select directory to which download node attributes
  --node NODE [NODE ...], --node-id NODE [NODE ...]
                        Node id.
  -r ROLE, --role ROLE  Role to assign for node.
  --net, --network      Node network configuration.
  --disk                Node disk configuration.
  -f, --force           Bypassing parameter validation.
"""
        node_help = self.run_cli_command(command_line="node --help")
        self.assertEqual(node_help.stdout, help_msg)

        node_call = self.run_cli_command(command_line="node")
        node_message = node_call.stdout.split("\n")
        #no nodes
        self.assertEqual(node_message[2], '')

        node_set_call = self.run_cli_command(
            command_line="node set", with_erros=True)
        #should not work without env id
        self.assertIn("required", node_set_call.stderr)

        node_remove_call = self.run_cli_command(
            command_line="node remove", with_erros=True)
        #should not work without env id
        self.assertIn("required", node_remove_call.stderr)

        node_network_call = self.run_cli_command(
            command_line="node --network", with_erros=True)
        #should not work without env id
        self.assertIn("required", node_network_call.stderr)

        node_disk_call = self.run_cli_command(
            command_line="node --disk", with_erros=True)
        self.assertIn("required", node_disk_call.stderr)