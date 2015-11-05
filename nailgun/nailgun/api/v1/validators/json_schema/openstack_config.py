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

# TODO(asaprykin): Make node_id and node_role
OPENSTACK_CONFIG = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'title': 'OpenstackConfig',
    'description': 'Openstack Configuration',
    'type': 'object',
    'properties': {
        'id': {'type': 'number'},
        'cluster_id': {'type': 'number', },
        'node_id': {'type': 'number'},
        'node_role': {'type': 'string'},
        'config': {'type': 'object'},
    },
    'required': ['cluster_id', 'config'],
    'oneOf': [
        {'required': ['node_id']},
        {'required': ['node_role']}
    ]
}
#
# OPENSTACK_CONFIG_COLLECTION = {
#     "$schema": "http://json-schema.org/draft-04/schema#",
#     "title": "OpenstackConfig collection",
#     "description": "Serialized OpenstackConfig collection",
#     "type": "object",
#     "items": OPENSTACK_CONFIG["properties"]
# }
