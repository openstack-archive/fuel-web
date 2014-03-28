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

from fuelclient.cli.actions import Action
import fuelclient.cli.arguments as Args
from fuelclient.cli.arguments import group
from fuelclient.objects.environment import Environment


class FactAction(Action):
    def __init__(self):
        self.args = [
            Args.get_env_arg(required=True),
            group(
                Args.get_delete_arg(
                    "Delete current {0} data.".format(self.action_name)
                ),
                Args.get_download_arg(
                    "Download current {0} data.".format(self.action_name)
                ),
                Args.get_upload_arg(
                    "Upload current {0} data.".format(self.action_name)
                ),
                Args.get_default_arg(
                    "Download default {0} data.".format(self.action_name)
                ),
                required=True
            ),
            Args.get_dir_arg(
                "Directory with {0} data.".format(self.action_name)
            ),
            Args.get_node_arg(
                "Node ids."
            ),
        ]
        self.flag_func_list = (
            "default", "upload", "delete", "download"
        )
        self.examples = """Examples:

    To download {func} information for some environment:
        fuel --env 1 {func} --download

    To get default {func} information for some environment:
        fuel --env 1 {func} --default

    To upload {func} information for some environment:
        fuel --env 1 {func} --upload

    It's possible to get default {func} information just for some nodes:
        fuel --env 1 {func} --default --node 1,2,3

    Also {func} information can be left or taken from specific directory:
        fuel --env 1 {func} --upload --dir path/to/some/directory
""".format(func=self.action_name)

    def default(self, params):
        env = Environment(params.env)
        env.write_facts_to_dir(
            self.action_name,
            env.get_default_facts(self.action_name, nodes=params.node),
            directory=params.dir
        )

    def upload(self, params):
        env = Environment(params.env)
        facts = getattr(env, self.read_method_name)(
            self.action_name,
            directory=params.dir
        )
        env.upload_facts(self.action_name, facts)
        self.serializer.print_to_output(
            facts,
            "{0} facts uploaded.".format(self.action_name)
        )

    def delete(self, params):
        env = Environment(params.env)
        env.delete_facts(self.action_name)
        self.serializer.print_to_output(
            {},
            "{0} facts deleted.".format(self.action_name)
        )

    def download(self, params):
        env = Environment(params.env)
        env.write_facts_to_dir(
            self.action_name,
            env.get_facts(self.action_name, nodes=params.node),
            directory=params.dir
        )

    @property
    def read_method_name(self):
        return "read_{0}_info".format(self.action_name)


class DeploymentAction(FactAction):
    """Show computed deployment facts for orchestrator
    """
    action_name = "deployment"


class ProvisioningAction(FactAction):
    """Show computed provisioning facts for orchestrator
    """
    action_name = "provisioning"
