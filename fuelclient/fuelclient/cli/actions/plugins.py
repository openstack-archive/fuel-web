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
        "version",
        "package_version",
    )

    def __init__(self):
        super(PluginAction, self).__init__()
        self.args = [
            Args.get_list_arg("List all available plugins."),
            Args.get_plugin_arg("Provide plugin id"),
            Args.get_plugin_install_arg("Install action"),
            Args.get_plugin_update_arg("Update action"),
            Args.get_dir_arg("Plugin path")
        ]
        self.flag_func_map = (
            ("install", self.install_plugin),
            ("update", self.update_plugin),
            (None, self.list),
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

    def install_plugin(self, params):
        """Enable plugin for environment
            fuel plugins --install --dir /tmp/plugin_sample
        """
        results = Plugins.install_plugin(params.dir)
        self.serializer.print_to_output(
            results,
            "Plugin from directory {0} was successfully installed.".format(
                params.dir))

    def update_plugin(self, params):
        """Disable plugin for environment
            fuel plugins --update --plugin 1 --dir /tmp/plugin_sample
        """
        results = Plugins.update_plugin(params.plugin, params.dir)
        self.serializer.print_to_output(
            results,
            "Plugin with id {0} from directory"
            " {1} was successfully updated.".format(params.plugin, params.dir))
