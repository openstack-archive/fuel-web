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
from fuelclient.objects.release import Release


class ReleaseAction(Action):
    """List and modify currently available releases
    """
    action_name = "release"

    def __init__(self):
        super(ReleaseAction, self).__init__()
        self.args = [
            group(
                Args.get_list_arg("List all available releases."),
                Args.get_config_arg("Configure release with --release"),
            ),
            Args.get_release_arg("Specify release id to configure"),
            Args.get_username_arg("Username for release credentials"),
            Args.get_password_arg("Password for release credentials"),
            Args.get_satellite_arg("Satellite server hostname"),
            Args.get_activation_key_arg("activation key")
        ]
        self.flag_func_map = (
            ("config", self.configure_release),
            (None, self.list)
        )

    def list(self, params):
        """Print all available releases:
                fuel release --list

           Print release with specific id=1:
                fuel release --rel 1
        """
        acceptable_keys = (
            "id",
            "name",
            "state",
            "operating_system",
            "openstack_version"
        )
        if params.release:
            release = Release(params.release)
            data = [release.get_fresh_data()]
        else:
            data = Release.get_all_data()
        self.serializer.print_to_output(
            data,
            format_table(
                data,
                acceptable_keys=acceptable_keys
            )
        )

    @check_all("release", "username", "password")
    def configure_release(self, params):
        """To configure RedHat release:
                fuel rel --rel <id of RedHat release> \\
                -c -U <username> -P <password>

           To configure RedHat release with satellite server:
                fuel rel --rel <...> -c -U <...> -P <...> \\
                --satellite-server-hostname <hostname> --activation-key <key>
        """
        release = Release(params.release)
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
