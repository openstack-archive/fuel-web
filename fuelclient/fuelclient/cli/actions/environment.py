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
from fuelclient.cli.actions import attrcheck
import fuelclient.cli.arguments as Args
from fuelclient.cli.arguments import group
from fuelclient.cli.formatting import format_table
from fuelclient.objects.environment import Environment


class EnvironmentAction(Action):
    """Create, list and modify currently existing environments(clusters)
    """
    action_name = "environment"

    def __init__(self):
        self.args = [
            Args.get_env_arg(),
            group(
                Args.get_list_arg(
                    "List all available environments."
                ),
                Args.get_set_arg(
                    "Set environment parameters (e.g name, deployment mode)"
                ),
                Args.get_delete_arg(
                    "Delete environment with specific env or name"
                ),
                Args.get_create_arg(
                    "Create a new environment with "
                    "specific release id and name."
                )
            ),
            Args.get_release_arg(
                "Release id"
            ),
            Args.get_name_arg(
                "environment name"
            ),
            Args.get_mode_arg(
                "Set deployment mode for specific environment."
            ),
            Args.get_net_arg(
                "Set network mode for specific environment."
            ),
            Args.get_nst_arg(
                "Set network segment type"
            )
        ]
        self.flag_func_map = (
            ("create", attrcheck(all)("name", "release"), self.create),
            (
                "set",
                (attrcheck(all)("env"), attrcheck(any)("name", "mode")),
                self.set
            ),
            ("delete", attrcheck(all)("env"), self.delete),
            (None, None, self.list)
        )
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

    def create(self, params):
        env = Environment.create(
            params.name,
            params.release,
            params.net,
            net_segment_type=params.nst
        )
        if params.mode:
            data = env.set(mode=params.mode)
        else:
            data = env.get_data()
        self.serializer.print_to_output(
            data,
            "Environment '{name}' with id={id}, mode={mode}"
            " and network-mode={net_provider} was created!"
            .format(**data)
        )

    def set(self, params):
        env = Environment(params.env, params=params)
        data = env.set(name=params.name, mode=params.mode)
        msg_templates = []
        if params.name:
            msg_templates.append(
                "Environment with id={id} was renamed to '{name}'.")
        if params.mode:
            msg_templates.append(
                "Mode of environment with id={id} was set to '{mode}'.")
        self.serializer.print_to_output(
            data,
            "\n".join(msg_templates).format(**data)
        )

    def delete(self, params):
        env = Environment(params.env, params=params)
        data = env.delete()
        self.serializer.print_to_output(
            data,
            "Environment with id={0} was deleted."
            .format(env.id)
        )

    def list(self, params):
        acceptable_keys = ("id", "status", "name", "mode",
                           "release_id", "changes")
        data = Environment.get_all_data()
        if params.env:
            data = filter(
                lambda x: x[u"id"] == int(params.env),
                data
            )
        self.serializer.print_to_output(
            data,
            format_table(
                data,
                acceptable_keys=acceptable_keys,
                subdict_keys=[("release_id", u"id")]
            )
        )
