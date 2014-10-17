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


class Plugins(BaseObject):

    class_api_path = "plugins/"

    @classmethod
    def get_plugins_for_cluster(cls, cluster_id):
        data = cls.connection.get_request(
            "clusters/{0}/plugins".format(cluster_id))
        return data

    @classmethod
    def enable_plugin(cls, cluster_id, plugin_id):
        url = "clusters/{0}/plugins/{1}".format(cluster_id, plugin_id)
        return cls.connection.post_request(url)

    @classmethod
    def disable_plugin(cls, cluster_id, plugin_id):
        url = "clusters/{0}/plugins/{1}".format(cluster_id, plugin_id)
        return cls.connection.delete_request(url)
