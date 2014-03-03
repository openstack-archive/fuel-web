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
from fuelclient.client import APIServer


class Node(BaseObject):
    def __init__(self):
        self.connection = APIServer()

    @classmethod
    def get_by_id(cls, _id):
        node = cls()
        node.id = _id
        return node

    def create(self, name, release):
        pass

