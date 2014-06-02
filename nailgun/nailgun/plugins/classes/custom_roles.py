#    Copyright 2013 Mirantis, Inc.
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

from nailgun.plugins.classes.base import NailgunPlugin


class CustomRolesPlugin(NailgunPlugin):

    role_names = None
    release_roles_metadata = None

    def custom_release_roles(self, *args, **kwargs):
        return self.release_roles_metadata

    def custom_pending_roles(self, node_id):
        plugin_roles_for_node = self.storage.search_records(
            record_type="pending_role",
            node_id=node_id
        )
        return [r["name"] for r in plugin_roles_for_node]

    def custom_roles(self, node_id):
        plugin_roles_for_node = self.storage.search_records(
            record_type="role",
            node_id=node_id
        )
        return [r["name"] for r in plugin_roles_for_node]

    def process_custom_pending_roles(self, node_id, new_pending_roles):
        orig_set = set(new_pending_roles)
        plugin_set = set(self.role_names)

        plugin_roles = list(orig_set & plugin_set)
        with self.storage as storage:
            for role in plugin_roles:
                storage.add_record(
                    "pending_role",
                    {"name": role, "node_id": node_id}
                )

        return list(orig_set ^ plugin_set)

    def process_custom_roles(self, node_id, new_roles):
        orig_set = set(new_roles)
        plugin_set = set(self.role_names)

        plugin_roles = list(orig_set & plugin_set)
        with self.storage as storage:
            for role in plugin_roles:
                storage.add_record(
                    "role",
                    {"name": role, "node_id": node_id}
                )

        return list(orig_set ^ plugin_set)
