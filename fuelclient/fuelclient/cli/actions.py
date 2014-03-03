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

from operator import attrgetter

from fuelclient.objects import Release
from fuelclient.cli.formatting import format_table
from fuelclient.cli.error import ArgumentException
from fuelclient.cli.formatting import quote_and_join
from fuelclient.cli.serializers import Serializer

import fuelclient.cli.arguments as Args


class Action(object):
    """
    Action class must have following attributes
    action_name, action_func, examples
    """
    action_name = None
    flag_func_map = None

    def action_func(self, params):
        self.serializer = Serializer(params=params)
        for predicate, argument_check, func in self.flag_func_map:
            if isinstance(predicate, str):
                predicate = attrgetter(predicate)
            if predicate and predicate(params):
                if argument_check:
                    if argument_check(params):
                        func(params)
                        break
                    else:
                        raise ArgumentException(
                            "{0} required!".format(
                                quote_and_join(
                                    "--" + arg for arg in argument_check.params
                                )
                            )
                        )
                else:
                    func(params)
                    break
            elif predicate is None:
                func(params)


def _(method):
    def outer(*args):
        def func(params):
            return method(getattr(params, arg) for arg in args)
        func.params = args
        return func
    return outer


class ReleaseAction(Action):
    action_name = "release"

    def __init__(self):
        self.serializer = None
        self.args = [
            Args.get_list_arg("List all available releases."),
            Args.get_release_arg("Specify release id to configure"),
            Args.get_config_arg("Configure release with --release"),
            Args.get_username_arg("Username for release credentials"),
            Args.get_password_arg("Password for release credentials"),
            Args.get_satellite_arg("Satellite server hostname"),
            Args.get_activation_key_arg("activation key")
        ]
        self.flag_func_map = (
            ("config", _(all)("rel", "username", "password"), self.configure_release),
            (None, None, self.list_releases)
        )
        self.examples = """Examples:

    Print all available releases:
        fuel release --list

    Print release with specific id=1:
        fuel release --rel 1

    To configure RedHat release:
        fuel rel --rel <id of RedHat release> -c -U <username> -P <password>

    To configure RedHat release with satellite server:
        fuel rel --rel <...> -c -U <...> -P <...> --satellite-server-hostname <hostname> --activation-key <key>
"""

    def list_releases(self, params):
        acceptable_keys = ("id", "name", "state", "operating_system", "version")
        if params.release:
            release = Release(params.release, params=params)
            data = [release.get_data()]
        else:
            data = Release.get_all_data()
        self.serializer.print_to_output(
            data,
            format_table(
                data,
                acceptable_keys=acceptable_keys
            )
        )

    def configure_release(self, params):
        release = Release(params.release, params=params)
        release_response = release.configure(
            params.username,
            params.password,
            satellite_server_hostname=None,
            activation_key=None
        )

        self.serializer.print_to_output(
            release_response,
            "Credentials for release with id={0}"
            " were modified."
            .format(release.id)
        )


class RoleAction(Action):
    action_name = "role"

    def __init__(self):
        self.args = [
            Args.get_list_arg("List all roles for specific release"),
            Args.get_release_arg("Release id", required=True)
        ]
        self.examples = """Examples:

    Print all available roles and their conflicts for some release with id=1:
        fuel role --rel 1
"""


class EnvironmentAction(Action):
    action_name = "environment"

    def __init__(self):
        self.args = [
            Args.get_env_arg(),
            Args.get_list_arg("List all available environments."),
            Args.get_set_arg("Set environment parameters (e.g name, deployment mode)"),
            Args.get_delete_arg("Delete environment with specific env or name"),
            Args.get_release_arg("Release id"),
            Args.get_create_arg("Create a new environment with specific release id and name."),
            Args.get_name_arg("environment name"),
            Args.get_mode_arg("Set deployment mode for specific environment."),
            Args.get_net_arg("Set network mode for specific environment."),
            Args.get_nst_arg("Set network segment type")
        ]
        self.examples = """Examples:

    Print all available environments:
        fuel env

    To create an environment with name MyEnv and release id=1 run:
        fuel env create --name MyEnv --rel 1

    By default it creates environment in multinode mode, and nova network mode,
    to specify other modes you can add optional arguments:
        fuel env create --name MyEnv --rel 1 --mode ha --network-mode neutron

    For changing environments name, mode or network mode exists set action:
        fuel --env 1 env set --name NewEmvName --mode ha_compact

    To delete the environment:
        fuel --env 1 env delete
"""


class NodeAction(Action):
        action_name = "node"

        def __init__(self):
            self.args = [
                Args.get_env_arg(),
                Args.get_list_arg("List all nodes."),
                Args.get_set_arg("Set role for specific node."),
                Args.get_delete_arg("Delete specific node from environment."),
                Args.get_default_arg("Get default network configuration of some node"),
                Args.get_download_arg("Download configuration of specific node"),
                Args.get_upload_arg("Upload configuration to specific node"),
                Args.get_dir_arg("Select directory to which download node attributes"),
                Args.get_node_arg("Node id."),
                Args.get_force_arg("Bypassing parameter validation."),
                Args.get_all_arg("Select all nodes."),
                Args.get_role_arg("Role to assign for node."),
                Args.get_network_arg("Node network configuration."),
                Args.get_disk_arg("Node disk configuration."),
                Args.get_deploy_arg("Deploy specific nodes."),
                Args.get_provision_arg("Provision specific nodes.")
            ]
            self.examples = """Examples:

    To list all available nodes:
        fuel node

    To filter them by environment:
        fuel --env-id 1 node

    Assign some nodes to environment with with specific roles:
        fuel --env 1 node set --node 1 --role controller
        fuel --env 1 node set --node 2,3,4 --role compute,cinder

    Remove some nodes from environment:
        fuel --env 1 node remove --node 2,3

    Remove nodes no matter to which environment they were assigned:
        fuel node remove --node 2,3,6,7

    Remove all nodes from some environment:
        fuel --env 1 node remove --all

    Download current or default disk, network, configuration for some node:
        fuel node --node-id 2 --disk --default
        fuel node --node-id 2 --network --download --dir path/to/directory

    Upload disk, network, configuration for some node:
        fuel node --node-id 2 --network --upload
        fuel node --node-id 2 --disk --upload --dir path/to/directory

    Deploy/Provision some node:
        fuel node --node-id 2 --provision
        fuel node --node-id 2 --deploy

    It's Possible to manipulate nodes with their short mac addresses:
        fuel node --node-id 80:ac
        fuel node remove --node-id 80:ac,5d:a2
"""


class FactAction(Action):
    def __init__(self):
        self.args = [
            Args.get_env_arg(),
            Args.get_delete_arg("Delete current {0} data.".format(self.action_name)),
            Args.get_download_arg("Download current {0} data.".format(self.action_name)),
            Args.get_upload_arg("Upload current {0} data.".format(self.action_name)),
            Args.get_default_arg("Download default {0} data.".format(self.action_name)),
            Args.get_dir_arg("Directory with {0} data.".format(self.action_name)),
            Args.get_node_arg("Node ids."),
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
            Args.get_env_arg(required=True)
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

actions_tuple = (
    ReleaseAction,
    RoleAction,
    EnvironmentAction,
    NodeAction,
    DeploymentAction,
    ProvisioningAction,
    StopAction,
    ResetAction
)

actions = dict(
    (action.action_name, action())
    for action in actions_tuple
)