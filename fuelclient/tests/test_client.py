# -*- coding: utf-8 -*-
#
#    Copyright 2013-2014 Mirantis, Inc.
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

from tests.base import BaseTestCase


class TestHandlers(BaseTestCase):

    def test_env_action(self):
        #check env help
        help_msgs = ["usage: fuel environment [-h]",
                     "[--list | --set | --delete | --create | --update]",
                     "optional arguments:", "--help", "--list", "--set",
                     "--delete", "--rel", "--env-create",
                     "--create", "--name", "--env-name", "--mode", "--net",
                     "--network-mode", "--nst", "--net-segment-type",
                     "--deployment-mode", "--update", "--env-update"]
        self.check_all_in_msg("env --help", help_msgs)
        #no clusters
        self.check_for_rows_in_table("env")

        for action in ("set", "create", "delete"):
            self.check_if_required("env {0}".format(action))

        #list of tuples (<fuel CLI command>, <expected output of a command>)
        expected_stdout = \
            [(
                "env --create --name=TestEnv --release=1",
                "Environment 'TestEnv' with id=1, mode=ha_compact and "
                "network-mode=nova_network was created!\n"
            ), (
                "--env-id=1 env set --name=NewEnv",
                ("Following attributes are changed for "
                 "the environment: name=NewEnv\n")
            ), (
                "--env-id=1 env set --mode=multinode",
                ("Following attributes are changed for "
                 "the environment: mode=multinode\n")
            )]

        for cmd, msg in expected_stdout:
            self.check_for_stdout(cmd, msg)

    def test_node_action(self):
        help_msg = ["fuel node [-h] [--env ENV]",
                    "[--list | --set | --delete | --network | --disk |"
                    " --deploy | --delete-from-db | --provision]", "-h",
                    "--help", " -s", "--default", " -d", "--download", " -u",
                    "--upload", "--dir", "--node", "--node-id", " -r",
                    "--role", "--net"]
        self.check_all_in_msg("node --help", help_msg)

        self.check_for_rows_in_table("node")

        for action in ("set", "remove", "--network", "--disk"):
            self.check_if_required("node {0}".format(action))

        self.load_data_to_nailgun_server()
        self.check_number_of_rows_in_table("node --node 9f:b7,9d:24,ab:aa", 3)

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

    def test_check_wrong_server(self):
        os.environ["SERVER_ADDRESS"] = "0"
        result = self.run_cli_command("-h", check_errors=True)
        self.assertEqual(result.stderr, '')
        del os.environ["SERVER_ADDRESS"]

    def test_wrong_credentials(self):
        result = self.run_cli_command("--os-username=a --os-password=a node",
                                      check_errors=True)
        self.assertEqual(result.stderr,
        '\n        Unauthorized: need authentication!\n'
        '        Please provide user and password via client --os-username '
        '--os-password\n        or modify "KEYSTONE_USER" and "KEYSTONE_PASS" '
        'in\n        /etc/fuel/client/config.yaml\n')

    def test_destroy_node(self):
        self.load_data_to_nailgun_server()
        self.run_cli_commands((
            "env create --name=NewEnv --release=1",
            "--env-id=1 node set --node 1 --role=controller"
        ))
        msg = ("Nodes with id [1] has been deleted from fuel db.\n"
               "You should still delete node from cobbler\n")
        self.check_for_stdout(
                "node --node 1 --delete-from-db",
                msg
            )

    def test_for_examples_in_action_help(self):
        actions = (
            "node", "stop", "deployment", "reset", "task", "network",
            "settings", "provisioning", "environment", "deploy-changes",
            "role", "release", "snapshot", "health"
        )
        for action in actions:
            self.check_all_in_msg("{0} -h".format(action), ("Examples",))

    def test_task_action_urls(self):
        self.check_all_in_msg(
            "task --task-id 1 --debug",
            [
                "GET http://127.0.0.1",
                "/api/v1/tasks/1/"
            ],
            check_errors=True
        )
        self.check_all_in_msg(
            "task --task-id 1 --delete --debug",
            [
                "DELETE http://127.0.0.1",
                "/api/v1/tasks/1/?force=0"
            ],
            check_errors=True
        )
        self.check_all_in_msg(
            "task --task-id 1 --delete --force --debug",
            [
                "DELETE http://127.0.0.1",
                "/api/v1/tasks/1/?force=1"
            ],
            check_errors=True
        )

    def test_get_release_list_without_errors(self):
        cmd = 'release --list'
        self.run_cli_command(cmd)


class TestUserActions(BaseTestCase):

    def test_change_password_params(self):
        cmd = "user --change-password"
        msg = "Expect password [--newpass NEWPASS]"
        result = self.run_cli_command(cmd, check_errors=True)
        self.assertTrue(msg, result)


class TestCharset(BaseTestCase):

    def test_charset_problem(self):
        self.load_data_to_nailgun_server()
        self.run_cli_commands((
            "env create --name=привет --release=1",
            "--env-id=1 node set --node 1 --role=controller",
            "env"
        ))


class TestFiles(BaseTestCase):

    def test_file_creation(self):
        self.load_data_to_nailgun_server()
        self.run_cli_commands((
            "env create --name=NewEnv --release=1",
            "--env-id=1 node set --node 1 --role=controller",
            "--env-id=1 node set --node 2,3 --role=compute"
        ))
        for action in ("network", "settings"):
            for format_ in ("yaml", "json"):
                self.check_if_files_created(
                    "--env 1 {0} --download --{1}".format(action, format_),
                    ("{0}_1.{1}".format(action, format_),)
                )
        command_to_files_map = (
            (
                "--env 1 deployment --default",
                (
                    "deployment_1",
                    "deployment_1/primary-controller_1.yaml",
                    "deployment_1/compute_2.yaml",
                    "deployment_1/compute_3.yaml"
                )
            ),
            (
                "--env 1 provisioning --default",
                (
                    "provisioning_1",
                    "provisioning_1/engine.yaml",
                    "provisioning_1/node-1.yaml",
                    "provisioning_1/node-2.yaml",
                    "provisioning_1/node-3.yaml"
                )
            ),
            (
                "--env 1 deployment --default --json",
                (
                    "deployment_1/primary-controller_1.json",
                    "deployment_1/compute_2.json",
                    "deployment_1/compute_3.json"
                )
            ),
            (
                "--env 1 provisioning --default --json",
                (
                    "provisioning_1/engine.json",
                    "provisioning_1/node-1.json",
                    "provisioning_1/node-2.json",
                    "provisioning_1/node-3.json"
                )
            ),
            (
                "node --node 1 --disk --default",
                (
                    "node_1",
                    "node_1/disks.yaml"
                )
            ),
            (
                "node --node 1 --network --default",
                (
                    "node_1",
                    "node_1/interfaces.yaml"
                )
            ),
            (
                "node --node 1 --disk --default --json",
                (
                    "node_1/disks.json",
                )
            ),
            (
                "node --node 1 --network --default --json",
                (
                    "node_1/interfaces.json",
                )
            )
        )
        for command, files in command_to_files_map:
            self.check_if_files_created(command, files)

    def check_if_files_created(self, command, paths):
        command_in_dir = "{0} --dir={1}".format(command, self.temp_directory)
        self.run_cli_command(command_in_dir)
        for path in paths:
            self.assertTrue(os.path.exists(
                os.path.join(self.temp_directory, path)
            ))


class TestDownloadUploadNodeAttributes(BaseTestCase):

    def test_upload_download_interfaces(self):
        self.load_data_to_nailgun_server()
        cmd = "node --node-id 1 --network"
        self.run_cli_commands((self.download_command(cmd),
                              self.upload_command(cmd)))

    def test_upload_download_disks(self):
        self.load_data_to_nailgun_server()
        cmd = "node --node-id 1 --disk"
        self.run_cli_commands((self.download_command(cmd),
                              self.upload_command(cmd)))


class TestDeployChanges(BaseTestCase):

    def test_deploy_changes_no_failure(self):
        self.load_data_to_nailgun_server()
        env_create = "env create --name=test --release=1"
        add_node = "--env-id=1 node set --node 1 --role=controller"
        deploy_changes = "deploy-changes --env 1"
        self.run_cli_commands((env_create, add_node, deploy_changes))
