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


class RoleAction(Action):
    """List all roles for specific release
    """
    action_name = "role"

    def __init__(self):
        super(RoleAction, self).__init__()
        self.args = [
            Args.get_list_arg("List all roles for specific release"),
            Args.get_release_arg("Release id", required=True)
        ]
        self.flag_func_map = (
            (None, self.list),
        )

    def list(self, params):
        """Print all available roles and their
           conflicts for some release with id=1:
                fuel role --rel 1
        """
        release = Release(params.release, params=params)
        data = release.get_fresh_data()
        acceptable_keys = ("name", "conflicts")
        roles = [
            {
                "name": role_name,
                "conflicts": ", ".join(
                    metadata.get("conflicts", ["-"])
                )
            } for role_name, metadata in data["roles_metadata"].iteritems()]
        self.serializer.print_to_output(
            roles,
            format_table(
                roles,
                acceptable_keys=acceptable_keys
            )
        )
