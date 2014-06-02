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


@plugin_hook('custom_pending_roles')
def get_custom_pending_roles(node_id):
    return []


@plugin_hook('process_custom_pending_roles')
def process_custom_pending_roles(node_id, new_pending_roles):
    return new_pending_roles


@plugin_hook('custom_roles')
def get_custom_roles(node_id):
    return []


@plugin_hook('process_custom_roles')
def process_custom_roles(node_id, new_roles):
    return new_roles
