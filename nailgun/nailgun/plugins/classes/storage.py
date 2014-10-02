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

from nailgun.plugins.classes.custom_roles import CustomRolesPlugin
from nailgun.plugins.classes.volumes import VolumesPlugin


class StoragePlugin(
    CustomRolesPlugin,
    VolumesPlugin
):

    def process_node_attrs(self, node, node_attrs):
        return node_attrs

    def process_cluster_attrs(self, cluster, cluster_attrs):
        return cluster_attrs
