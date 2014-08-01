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
from fuelclient.cli.error import ArgumentException
from fuelclient.client import APIClient


class UserAction(Action):
    """Change password for user
    """
    action_name = "user"

    def __init__(self):
        super(UserAction, self).__init__()
        self.args = (
            Args.get_new_password_arg(),
            Args.get_change_password_arg("Change user password")
        )

        self.flag_func_map = (
            ("change-password", self.change_password),
        )

    def change_password(self, params):
        """To change user password:
                fuel user change-password
        """
        if params.newpass:
            APIClient.update_own_password(params.newpass)
        else:
            raise ArgumentException(
                "Expect password [--newpass NEWPASS]")
