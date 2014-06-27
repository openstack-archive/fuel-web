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
from fuelclient.cli.actions.base import check_all
import fuelclient.cli.arguments as Args
from fuelclient.cli.arguments import group
from fuelclient.cli.formatting import format_table
from fuelclient.objects.environment import Environment


class EnvironmentAction(Action):
    """Create, list and modify currently existing environments(clusters)
    """
    action_name = "environment"

    def __init__(self):
        super(EnvironmentAction, self).__init__()
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
                ),
                Args.get_update_arg(
                    "Update OS to specified release id for given env."
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
            ("create", self.create),
            ("set", self.set),
            ("delete", self.delete),
            ("update", self.update),
            (None, self.list)
        )

    @check_all("name", "release")
    def create(self, params):
        """To create an environment with name MyEnv and release id=1 run:
                fuel env create --name MyEnv --rel 1

           By default it creates environment in multinode mode, and nova
           network mode, to specify other modes add optional arguments:
                fuel env create --name MyEnv --rel 1 \\
                --mode ha --network-mode neutron
        """
        env = Environment.create(
            params.name,
            params.release,
            params.net,
            net_segment_type=params.nst
        )

        if params.mode:
            data = env.set({'mode': params.mode})
        else:
            data = env.get_fresh_data()

        self.serializer.print_to_output(
            data,
            u"Environment '{name}' with id={id}, mode={mode}"
            u" and network-mode={net_provider} was created!"
            .format(**data)
        )

    @check_all("env")
    def set(self, params):
        """For changing environments name, mode
           or network mode exists set action:
                fuel --env 1 env set --name NewEmvName --mode ha_compact
        """
        acceptable_params = ('mode', 'name', 'pending_release_id')

        env = Environment(params.env, params=params)

        # forming message for output and data structure for request body
        # TODO(aroma): make it less ugly
        msg_template = ("Following attributes are changed for "
                        "the environment: {env_attributes}")

        env_attributes = []
        update_kwargs = dict()
        for param_name in acceptable_params:
            attr_value = getattr(params, param_name, None)
            if attr_value:
                update_kwargs[param_name] = attr_value
                env_attributes.append(
                    ''.join([param_name, '=', str(attr_value)])
                )

        data = env.set(update_kwargs)
        env_attributes = ', '.join(env_attributes)
        self.serializer.print_to_output(
            data,
            msg_template.format(env_attributes=env_attributes)
        )

    @check_all("env")
    def delete(self, params):
        """To delete the environment:
                fuel --env 1 env delete
        """
        env = Environment(params.env, params=params)
        data = env.delete()
        self.serializer.print_to_output(
            data,
            "Environment with id={0} was deleted."
            .format(env.id)
        )

    def list(self, params):
        """Print all available environments:
                fuel env
        """
        acceptable_keys = ("id", "status", "name", "mode",
                           "release_id", "changes", "pending_release_id")
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
                acceptable_keys=acceptable_keys
            )
        )

    def update(self, params):
        """Update environment to given OS release
                fuel env --env 1 --update --release 1
        """
        params.pending_release_id = params.release
        self.set(params)

        env = Environment(params.env, params=params)
        update_task = env.update_env()

        msg = ("Update process for environment has been started. "
               "Update task id is {0}".format(update_task.id))

        self.serializer.print_to_output(
            {},
            msg
        )
