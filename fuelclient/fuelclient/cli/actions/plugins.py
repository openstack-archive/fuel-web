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
from fuelclient.cli.formatting import format_table
from fuelclient.objects.plugins import Plugins


class PluginAction(Action):
    """List and modify currently available releases
    """
    action_name = "plugins"

    acceptable_keys = (
        "id",
        "name",
        "package_version",
        "releases"
    )

    def __init__(self):
        super(PluginAction, self).__init__()
        self.args = [
            Args.get_list_arg("List all available plugins."),
            Args.get_env_arg(required=False),
            Args.get_plugin_arg("Provide plugin id"),
            Args.get_enable_arg("Enable action"),
            Args.get_disable_arg("Disable action")
        ]
        self.flag_func_map = (
            (None, self.list),
            ("env", self.list_for_environment),
            ("enable", self.enable_plugin),
            ("disable", self.disable_plugin),
        )

    def list(self, params):
        """Print all available plugins:
                fuel plugins --list
        """
        plugins = Plugins.get_all_data()
        self.serializer.print_to_output(
            plugins,
            format_table(
                plugins,
                acceptable_keys=self.acceptable_keys
            )
        )

    def list_for_environment(self, params):
        """List all enabled plugins for environment
            fuel plugins --list --env 1
        """
        plugins = Plugins.get_plugins_for_cluster(params.env)
        self.serializer.print_to_output(
            plugins,
            format_table(
                plugins,
                acceptable_keys=self.acceptable_keys
            )
        )

    def enable_plugin(self, params):
        """Enable plugin for environment
            fuel plugins --enable --env 1 --plugin 1
        """
        results = Plugins.enable_plugin(params.env, params.plugin)
        self.serializer.print_to_output(
            results,
            "Plugin with id {0} was enabled for cluster with id {1}."
            .format(str(params.env), str(params.plugin)))

    def disable_plugin(self, params):
        """Disable plugin for environment
            fuel plugins --disable --env 1 --plugin 1
        """
        results = Plugins.disable_plugin(params.env, params.plugin)
        self.serializer.print_to_output(
            results,
            "Plugin with id {0} was disabled for cluster with id {1}."
            .format(str(params.env), str(params.plugin)))
