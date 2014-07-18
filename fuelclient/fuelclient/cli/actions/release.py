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
from fuelclient.objects.release import Release


class ReleaseAction(Action):
    """List and modify currently available releases
    """
    action_name = "release"

    def __init__(self):
        super(ReleaseAction, self).__init__()
        self.args = [
            Args.get_release_arg('Specify particular release id'),
            Args.get_list_arg("List all available releases."),
        ]
        self.flag_func_map = (
            (None, self.list),
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
            "version"
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
