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

from fuelclient.client import APIServer
from fuelclient.cli.serializers import Serializer


class BaseObject(object):

    class_api_path = None
    instance_api_path = None
    connection = APIServer()
    serializer = Serializer()

    def __init__(self, params=None):
        self.connection = APIServer(params=params)
        self.serializer = Serializer(params=params)
        self._params = params

    def get_data(self):
        return self.connection.get_request(
            self.instance_api_path.format(self.id))

    @classmethod
    def get_all_data(cls):
        return cls.connection.get_request(cls.class_api_path)