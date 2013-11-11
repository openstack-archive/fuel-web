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


from fuel_cli.tests.base import BaseTestCase


class TestHandlers(BaseTestCase):
    def test_env_print(self):
        ns = self.ns
        main_help = ns.run_cli_command(command_line="-h")
        node_listing = ns.run_cli_command(command_line="node")
        node_help = ns.run_cli_command(command_line="node -h")
        relsease_help = ns.run_cli_command(command_line="rel -h")
        # Get information about Releases and configure them
        # Get full list of available Releases
        release_list = ns.run_cli_command(command_line="rel")
        # Get information on specific Release
        ns.run_cli_command(command_line="rel --rel 1")
        # Configure RedHat Release by adding specific credentials
        ns.run_cli_command(command_line="rel config --rel 2 --user Misha --pass valid")
        # Get information about Environments and change them
        # List all available environments
        ns.run_cli_command(command_line="env")
        ns.run_cli_command(command_line="environment")
        ns.run_cli_command(command_line="env list")
        # List specific environment
        ns.run_cli_command(command_line="env --env 1")
        # Create new environment with specific name and Release
        ns.run_cli_command(command_line="env create --name env_name --release 1")
        # Renaming environment with id=1 to 'New_env_name'
        ns.run_cli_command(command_line="env set --env 1 --name New_env_name")
        # Get information about Nodes and check their attributes, assign to envs e.t.c
        # List all available Nodes
        ns.run_cli_command(command_line="node")
        ns.run_cli_command(command_line="node list")
        ns.run_cli_command(command_line="node --list")
        # List all Nodes assigned to specific environment
        ns.run_cli_command(command_line="node --env 2")
        # Assign some nodes to environemnt with id=1 with specific roles
        ns.run_cli_command(command_line="node set --node 1 --role controller --env 1")
        ns.run_cli_command(command_line="node set --node 2,3,4 --role compute,cinder --env 1")
        # Remove some nodes from environment
        ns.run_cli_command(command_line="node remove --node 2,3 --env 1")
        # Can do it without --env
        ns.run_cli_command(command_line="node remove --node 2,3")
        # Also you can remove all nodes from environment
        ns.run_cli_command(command_line="node remove --env 1")
        # Deploying cahnges
        ns.run_cli_command(command_line="deploy --env 1")
        # In case of custom modification of deployment facts
        # Get default facts
        ns.run_cli_command(command_line="deployment default --env 1")
        # Download default facts to specific derictory
        ns.run_cli_command(command_line="deployment default --env 1 --dir some/dir/")
        # Upload facts to Nailgun
        ns.run_cli_command(command_line="deployment upload --env 1")
        # Upload facts from specific derectory to Nailgun
        ns.run_cli_command(command_line="deployment upload --env 1 --dir some/dir/")
        # Download current facts
        ns.run_cli_command(command_line="deployment download --env 1")
        # Delete uploaded facts on Nailgun
        ns.run_cli_command(command_line="deployment delete --env 1")
        # In case of custom modification of provisioning facts
        ns.run_cli_command(command_line="provisioning default --env 1")
        ns.run_cli_command(command_line="provisioning upload --env 1")
        ns.run_cli_command(command_line="provisioning download --env 1")
        ns.run_cli_command(command_line="provisioning delete --env 1")
        # To Download network configuration for specific environment
        ns.run_cli_command(command_line="network --download --env 1")
        # To Upload network configuration for specific environment
        ns.run_cli_command(command_line="network --upload --env 1")
        # To Verify network configuration for local files
        ns.run_cli_command(command_line="network --verify --env 1")
        # To Download default environment configuration for specific environment
        ns.run_cli_command(command_line="settings default --env 1")
        # To Download environment configuration for specific environment
        ns.run_cli_command(command_line="settings download --env 1")
        # To Upload environment configuration for specific environment
        ns.run_cli_command(command_line="settings upload --env 1")
        # List all tasks
        ns.run_cli_command(command_line="task")
        # To delete specific task
        ns.run_cli_command(command_line="task delete --task-id 15")
        # --json output modifier, all most any request will return json of the request to stdout
        ns.run_cli_command(command_line="env --env 1 --json")
        # with --debug all HTTP request to Nailgun server will be printed to stdout
        ns.run_cli_command(command_line="node list --debug")
