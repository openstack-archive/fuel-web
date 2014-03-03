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

from fuelclient.objects import BaseObject
from fuelclient.cli.error import ArgumentException


class Release(BaseObject):

    class_api_path = "releases/"
    instance_api_path = "releases/{0}/"

    def __init__(self, _id, params=None):
        super(Release, self).__init__(params=params)
        self.id = _id

    @classmethod
    def init_with_data(cls, data):
        return cls(data["id"])

    def configure(self, username, password,
                  satellite_server_hostname=None, activation_key=None):
        data = {
            "release_id": self.id,
            "username": username,
            "password": password
        }
        satellite_flags = [satellite_server_hostname,
                           activation_key]

        if not any(satellite_flags):
            data.update({
                "license_type": "rhsm",
                "satellite": "",
                "activation_key": ""
            })
        elif all(satellite_flags):
            data.update({
                "license_type": "rhn",
                "satellite": satellite_server_hostname,
                "activation_key": activation_key
            })
        else:
            raise ArgumentException(
                'RedHat satellite settings requires both a'
                ' "--satellite-server-hostname" and '
                'a "--activation-key" flags.'
            )
        release_response = self.connection.post_request(
            "redhat/setup/",
            data
        )
        return release_response

    @classmethod
    def get_all(cls):
        map(cls.init_with_data, cls.get_all_data())
