#    Copyright 2015 Mirantis, Inc.
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

_OPENSTACK_CONFIG_BASE = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'title': 'OpenstackConfig',
    'description': 'Openstack Configuration',
    'type': 'object',
    'properties': {
        'id': {'type': 'number'},
        'cluster_id': {'type': 'number', },
        'node_id': {'type': 'number'},
        'node_role': {'type': 'string'},
        'configuration': {'type': 'object'},
    },
}

OPENSTACK_CONFIG = dict(
    _OPENSTACK_CONFIG_BASE,
    required=['cluster_id', 'configuration'],
)

OPENSTACK_CONFIG_EXECUTE = dict(
    _OPENSTACK_CONFIG_BASE,
    required=['cluster_id']
)

OPENSTACK_CONFIG_QUERY = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'title': 'OpenstackConfig query',
    'description': 'URL query for Openstack Configuration filter',
    'type': 'object',
    'properties': {
        'cluster_id': {'type': 'number'},
        'node_id': {'type': 'number'},
        'node_role': {'type': 'string'},
        'is_active': {'type': 'number'},
    },
    'required': ['cluster_id'],
}
