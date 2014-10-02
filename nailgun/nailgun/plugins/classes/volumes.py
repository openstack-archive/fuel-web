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

from nailgun.plugins.classes.base import NailgunPlugin


class VolumesPlugin(NailgunPlugin):

    volumes_roles_mapping = None
    volumes = None
    generators = None

    def custom_volumes_mapping(self, *args, **kwargs):
        volumes_roles_mapping = self.config['volumes_roles_mapping']
        for role, mapping in volumes_roles_mapping.iteritems():
            for alloc in mapping:
                alloc["plugin_name"] = self.plugin_name
        return volumes_roles_mapping

    def custom_volumes(self, *args, **kwargs):
        volumes = self.config['volumes']
        for vol in volumes:
            vol["plugin_name"] = self.plugin_name
        return volumes

    def custom_volumes_generators(self, *args, **kwargs):
        return self.generators

    def custom_volumes_for_disk(self, node_id, disk_id):
        volumes = self.storage.search_records(
            record_type="volume",
            node_id=node_id,
            disk_id=disk_id
        )
        return [v.data["data"] for v in volumes]

    def process_volumes(self, volumes, disk_id, node_id):
        res = []
        with self.storage as storage:
            for volume in volumes:
                if volume.get("plugin_name") == self.plugin_name:
                    storage.add_record(
                        "volume",
                        {
                            "node_id": node_id,
                            "disk_id": disk_id,
                            "data": volume,
                        }
                    )
                else:
                    res.append(volume)
        return res

    def process_volumes_metadata(self, volumes_metadata):
        volumes_mapping = self.custom_volumes_mapping()
        for role_name, volumes_meta in volumes_mapping.iteritems():
            volumes_metadata["volumes_roles_mapping"][role_name] = volumes_meta
        for vol in self.custom_volumes():
            volumes_metadata["volumes"].append(vol)
        return volumes_metadata
