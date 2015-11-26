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

_base_config = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'type': 'object',
    'additionalProperties': False,
}

_base_properties = {
    'cluster_id': {'type': 'number', },
    'node_id': {'type': 'number'},
    'node_role': {'type': 'string'},
}

OPENSTACK_CONFIG = {
    'title': 'OpenstackConfig',
    'description': 'Openstack Configuration',
    'properties': {
        'id': {'type': 'number'},
        'configuration': {'type': 'object'},
    },
    'required': ['cluster_id', 'configuration'],
}

OPENSTACK_CONFIG_EXECUTE = {
    'title': 'OpenstackConfig execute',
    'description': 'Openstack Configuration filters for execute',
    'properties': {
        'id': {'type': 'number'},
        'force': {'type': 'boolean'}
    },
    'required': ['cluster_id'],
}

OPENSTACK_CONFIG_QUERY = {
    'title': 'OpenstackConfig query',
    'description': 'URL query for Openstack Configuration filter',
    'properties': {
        'is_active': {'type': 'boolean'},
        'cluster_id': {'type': 'number'},
    },
    'required': ['cluster_id'],
}

for schema in (OPENSTACK_CONFIG, OPENSTACK_CONFIG_EXECUTE,
               OPENSTACK_CONFIG_QUERY):
    schema.update(_base_config)
    schema['properties'].update(_base_properties)
