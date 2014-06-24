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


class SettingsAction(Action):
    """Show or modify environment settings
    """
    action_name = "settings"

    def __init__(self):
        super(SettingsAction, self).__init__()
        self.args = (
            Args.get_env_arg(required=True),
            group(
                Args.get_download_arg("Modify current configuration."),
                Args.get_default_arg("Open default configuration."),
                Args.get_upload_arg("Save current changes in configuration."),
                required=True
            ),
            Args.get_dir_arg("Directory with configuration data.")
        )
        self.flag_func_map = (
            ("upload", self.upload),
            ("default", self.default),
            ("download", self.download)
        )

    def upload(self, params):
        """To upload settings for some environment from some directory:
                fuel --env 1 settings --upload --dir path/to/directory
        """
        env = Environment(params.env)
        settings_data = env.read_settings_data(
            directory=params.dir,
            serializer=self.serializer
        )
        env.set_settings_data(settings_data)
        print("Settings configuration uploaded.")

    def default(self, params):
        """To download default settings for some environment in some directory:
                fuel --env 1 settings --default --dir path/to/directory
        """
        env = Environment(params.env)
        default_data = env.get_default_settings_data()
        settings_file_path = env.write_settings_data(
            default_data,
            directory=params.dir,
            serializer=self.serializer)
        print(
            "Default settings configuration downloaded to {0}."
            .format(settings_file_path)
        )

    def download(self, params):
        """To download settings for some environment in this directory:
                fuel --env 1 settings --download
        """
        env = Environment(params.env)
        settings_data = env.get_settings_data()
        settings_file_path = env.write_settings_data(
            settings_data,
            directory=params.dir,
            serializer=self.serializer)
        print(
            "Settings configuration for environment with id={0}"
            " downloaded to {1}"
            .format(env.id, settings_file_path)
        )
