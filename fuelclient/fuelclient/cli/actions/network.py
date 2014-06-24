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


class NetworkAction(Action):
    """Show or modify network settings of specific environments
    """
    action_name = "network"

    def __init__(self):
        super(NetworkAction, self).__init__()
        self.args = (
            Args.get_env_arg(required=True),
            Args.get_dir_arg("Directory with network data."),
            group(
                Args.get_download_arg(
                    "Download current network configuration."),
                Args.get_verify_arg(
                    "Verify current network configuration."),
                Args.get_upload_arg(
                    "Upload changed network configuration."),
                required=True
            )
        )
        self.flag_func_map = (
            ("upload", self.upload),
            ("verify", self.verify),
            ("download", self.download)
        )

    def upload(self, params):
        """To upload network configuration from some
           directory for some environment:
                fuel --env 1 network --upload --dir path/to/directory
        """
        env = Environment(params.env)
        network_data = env.read_network_data(
            directory=params.dir,
            serializer=self.serializer
        )
        env.set_network_data(network_data)
        print(
            "Network configuration uploaded."
        )

    def verify(self, params):
        """To verify network configuration from some directory
           for some environment:
                fuel --env 1 network --verify --dir path/to/directory
        """
        env = Environment(params.env)
        response = env.verify_network()
        print(
            "Verification status is '{status}'. message: {message}"
            .format(**response)
        )

    def download(self, params):
        """To download network configuration in this
           directory for some environment:
                fuel --env 1 network --download
        """
        env = Environment(params.env)
        network_data = env.get_network_data()
        network_file_path = env.write_network_data(
            network_data,
            directory=params.dir,
            serializer=self.serializer)
        print(
            "Network configuration for environment with id={0}"
            " downloaded to {1}"
            .format(env.id, network_file_path)
        )
