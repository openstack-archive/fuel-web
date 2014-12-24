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

from fuelclient.cli import error

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
            Args.get_plugin_install_arg("Install action"),
            Args.get_plugin_remove_arg("Remove action"),
            Args.get_force_arg("Update action"),
        ]
        self.flag_func_map = (
            ("install", self.install),
            ("remove", self.remove),
            (None, self.list),
        )

    def list(self, params):
        """Print all available plugins:
                fuel plugins
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

    def install(self, params):
        """Enable plugin for environment
            fuel plugins --install /tmp/plugin_sample.fb
        """
        results = Plugins.install_plugin(params.install, params.force)
        self.serializer.print_to_output(
            results,
            "Plugin {0} was successfully installed.".format(
                params.install))

    def remove(self, params):
        """Remove plugin from environment
            fuel plugins --remove plugin_sample
            fuel plugins --remove plugin_sample==1.0.1
        """
        s = params.remove.split('==')
        plugin_name = s[0]
        plugin_version = None
        if len(s) >= 2:
            plugin_version = s[1]
        elif len(s) > 2:
            raise error.ArgumentException(
                'Syntax: fuel plugins --remove fuel_plugin==1.0')
        results = Plugins.remove_plugin(
            plugin_name, plugin_version=plugin_version, force=params.force)
        self.serializer.print_to_output(
            results,
            "Plugin {0} was successfully removed.".format(
                params.remove))
