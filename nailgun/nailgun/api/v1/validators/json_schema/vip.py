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

VIP_INFO_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "required": ["name"],
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 255},
        "network_role": {"type": "string", "maxLength": 255},
        "namespace": {"type": "string", "maxLength": 255},
        'node_roles': {
            'type': 'array',
            'items': {'type': 'string', "maxLength": 255}
        },
        "alias": {"type": "string", "maxLength": 255},
        "manual": {"type": "boolean"},
    }
}

VIPS_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'type': 'array',
    'items': VIP_INFO_SCHEMA
}
