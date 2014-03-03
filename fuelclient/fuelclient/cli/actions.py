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

from fuelclient.cli.arguments import get_env_arg
from fuelclient.cli.arguments import get_delete_arg
from fuelclient.cli.arguments import get_download_arg
from fuelclient.cli.arguments import get_upload_arg
from fuelclient.cli.arguments import get_default_arg
from fuelclient.cli.arguments import get_dir_arg
from fuelclient.cli.arguments import get_node_arg


class Action:
    """
    Action class must have following attributes
    action_name, action_func, examples
    """
    def action_func(self, params):
        for predicate, func in self.flag_func_map:
            if predicate(params):
                func(params)
                break


class FactAction(Action):
    def __init__(self):
        self.args = [
            get_env_arg(),
            get_delete_arg("Delete current {0} data.".format(self.action_name)),
            get_download_arg("Download current {0} data.".format(self.action_name)),
            get_upload_arg("Upload current {0} data.".format(self.action_name)),
            get_default_arg("Download default {0} data.".format(self.action_name)),
            get_dir_arg("Directory with {0} data.".format(self.action_name)),
            get_node_arg("Node ids."),
        ]
        self.flag_func_map = (

        )
        self.examples = \
            """Examples:

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


class DeploymentAction(FactAction):
    action_name = "deployment"


class ProvisioningAction(FactAction):
    action_name = "provisioning"


class InterruptAction(Action):

    def __init__(self):
        self.args = [
            get_env_arg(required=True)
        ]
        self.flag_func_map = (

        )
        self.examples = """Examples:

    To {func} some environment:
        fuel --env 1 {func}
""".format(func=self.action_name)


class StopAction(InterruptAction):
    action_name = "stop"


class ResetAction(InterruptAction):
    action_name = "reset"

actions_tuple = (DeploymentAction, ProvisioningAction, StopAction, ResetAction)

actions = dict((action.action_name, action()) for action in actions_tuple)