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

from operator import attrgetter

from fuelclient.objects.base import BaseObject


class NodeGroup(BaseObject):

    class_api_path = "nodegroups/"
    instance_api_path = "nodegroups/{0}/"

    @property
    def env_id(self):
        return self.get_fresh_data()["cluster"]

    @property
    def name(self):
        return self.get_fresh_data()["name"]

    @classmethod
    def create(cls, name, cluster_id):
        return cls.connection.post_request(
            cls.class_api_path,
            {'cluster_id': cluster_id, 'name': name},
        )

    @classmethod
    def delete(cls, group_id):
        return cls.connection.delete_request(
            cls.instance_api_path.format(group_id)
        )

    @classmethod
    def assign(cls, group_id, nodes):
        return cls.connection.post_request(
            cls.instance_api_path.format(group_id),
            nodes
        )


class NodeGroupCollection(object):

    def __init__(self, groups):
        self.collection = groups

    @classmethod
    def init_with_ids(cls, ids):
        return cls(map(NodeGroup, ids))

    @classmethod
    def init_with_data(cls, data):
        return cls(map(NodeGroup.init_with_data, data))

    def __str__(self):
        return "node groups [{0}]".format(
            ", ".join(map(lambda n: str(n.id), self.collection))
        )

    def __iter__(self):
        return iter(self.collection)

    @property
    def data(self):
        return map(attrgetter("data"), self.collection)

    @classmethod
    def get_all(cls):
        return cls(NodeGroup.get_all())

    def filter_by_env_id(self, env_id):
        self.collection = filter(
            lambda group: group.env_id == env_id,
            self.collection
        )
