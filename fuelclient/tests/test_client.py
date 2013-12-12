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
        help_msgs = ["usage: fuel [global optional args]",
                     "environment [-h] [-l] [-s] [--delete]",
                     "optional arguments:", "--help", "--list", "--set",
                     "--delete", "--rel", "--release", "--env-create,",
                     "--create", "--name", "--env-name", "--mode", "--net",
                     "--network-mode", "--nst", "--net-segment-type",
                     "--deployment-mode"]
        self.check_all_in_msg("env --help", help_msgs)
        #no clusters
        self.check_for_rows_in_table("env")

        for action in ("set", "create", "delete"):
            self.check_if_required("env {0}".format(action))

        #list of tuples (<fuel CLI command>, <expected output of a command>)
        expected_stdout = \
            [(
                "env create --name=TestEnv --release=1",
                "Environment 'TestEnv' with id=1, mode=multinode and "
                "network-mode=nova_network was created!\n"
            ), (
                "--env-id=1 env set --name=NewEnv",
                "Environment with id=1 was renamed to 'NewEnv'.\n"
            ), (
                "--env-id=1 env set --mode=ha",
                "Mode of environment with id=1 was set to 'ha'.\n"
            )]

        for cmd, msg in expected_stdout:
            self.check_for_stdout(cmd, msg)

    def test_node_action(self):
        help_msg = ["usage: fuel [global optional args] node [-h] ",
                    "[-l] [-s] [--delete] [--default]", "-h", "--help", "-l",
                    "--list", "-s", "--set", "--delete", "--default", "-d",
                    "--download", "-u", "--upload", "--dir", "--node",
                    "--node-id", "-r", "--role", "--net", "--network",
                    "--disk", "-f", "--force", "--deploy", "--provision"]
        self.check_all_in_msg("node --help", help_msg)

        self.check_for_rows_in_table("node")

        for action in ("set", "remove", "--network", "--disk"):
            self.check_if_required("node {0}".format(action))

    def test_selected_node_deploy_or_provision(self):
        self.load_data_to_nailgun_server()
        self.run_cli_commands((
            "env create --name=NewEnv --release=1",
            "--env-id=1 node set --node 1 --role=controller"
        ))
        commands = ("--provision", "--deploy")
        for action in commands:
            self.check_if_required("--env-id=1 node {0}".format(action))
        messages = (
            "Started provisioning nodes [1].\n",
            "Started deploying nodes [1].\n"
        )
        for cmd, msg in zip(commands, messages):
            self.check_for_stdout(
                "--env-id=1 node {0} --node=1".format(cmd),
                msg
            )
