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

from nailgun.plugins import plugin_hook


@plugin_hook('custom_release_roles')
def get_custom_roles():
    return []


@plugin_hook('process_volumes_metadata')
def process_volumes_metadata(volumes_metadata):
    return volumes_metadata


@plugin_hook('process_volumes')
def process_volumes(volumes, disk_id, node_id):
    return volumes


@plugin_hook('custom_volumes_for_disk')
def get_custom_volumes_for_disk(node_id, disk_id):
    return []


@plugin_hook('custom_volumes_mapping')
def get_custom_volumes_mapping():
    return []


@plugin_hook('custom_volumes')
def get_custom_volumes():
    return []


@plugin_hook('custom_volumes_generators')
def get_custom_volumes_generators():
    return {}
