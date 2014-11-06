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

from fuelclient.objects.base import BaseObject


class Release(BaseObject):

    class_api_path = "releases/"
    instance_api_path = "releases/{0}/"
    networks_path = 'releases/{0}/networks'

    @classmethod
    def get_all(cls):
        map(cls.init_with_data, cls.get_all_data())

    def get_networks(self):
        url = self.networks_path.format(self.id)
        return self.connection.get_request(url)

    def update_networks(self, data):
        url = self.networks_path.format(self.id)
        return self.connection.put_request(url, data)
