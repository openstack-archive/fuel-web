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

from fuelclient.cli.actions.base import Action
import fuelclient.cli.arguments as Args
from fuelclient.cli.arguments import group
from fuelclient.objects.environment import Environment


class FactAction(Action):

    action_name = None

    def __init__(self):
        super(FactAction, self).__init__()
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
        self.flag_func_map = (
            ("default", self.default),
            ("upload", self.upload),
            ("delete", self.delete),
            ("download", self.download)
        )

    def default(self, params):
        """To get default {action_name} information for some environment:
                fuel --env 1 {action_name} --default

            It's possible to get default {action_name} information
            just for some nodes:
                fuel --env 1 {action_name} --default --node 1,2,3
        """
        env = Environment(params.env)
        dir_name = env.write_facts_to_dir(
            self.action_name,
            env.get_default_facts(self.action_name, nodes=params.node),
            directory=params.dir,
            serializer=self.serializer
        )
        print(
            "Default {0} info was downloaded to {1}".format(
                self.action_name,
                dir_name
            )
        )

    def upload(self, params):
        """To upload {action_name} information for some environment:
                fuel --env 1 {action_name} --upload
        """
        env = Environment(params.env)
        facts = env.read_fact_info(
            self.action_name,
            directory=params.dir,
            serializer=self.serializer
        )
        env.upload_facts(self.action_name, facts)
        print("{0} facts were uploaded.".format(self.action_name))

    def delete(self, params):
        """Also {action_name} information can be left or
           taken from specific directory:
                fuel --env 1 {action_name} --upload \\
                --dir path/to/some/directory
        """
        env = Environment(params.env)
        env.delete_facts(self.action_name)
        print("{0} facts deleted.".format(self.action_name))

    def download(self, params):
        """To download {action_name} information for some environment:
                fuel --env 1 {action_name} --download
        """
        env = Environment(params.env)
        dir_name = env.write_facts_to_dir(
            self.action_name,
            env.get_facts(self.action_name, nodes=params.node),
            directory=params.dir,
            serializer=self.serializer
        )
        print(
            "Current {0} info was downloaded to {1}".format(
                self.action_name,
                dir_name
            )
        )


class DeploymentAction(FactAction):
    """Show computed deployment facts for orchestrator
    """
    action_name = "deployment"


class ProvisioningAction(FactAction):
    """Show computed provisioning facts for orchestrator
    """
    action_name = "provisioning"
