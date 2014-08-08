# -*- coding: utf-8 -*-

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

import copy

from nailgun import consts

from nailgun.api.v1.validators.json_schema.base_types import ID
from nailgun.api.v1.validators.json_schema.base_types import IP_ADDRESS
from nailgun.api.v1.validators.json_schema.base_types import MAC_ADDRESS
from nailgun.api.v1.validators.json_schema.base_types import NET_ADDRESS
from nailgun.api.v1.validators.json_schema.base_types \
    import NON_NEGATIVE_INTEGER
from nailgun.api.v1.validators.json_schema.base_types import NULLABLE_ID
from nailgun.api.v1.validators.json_schema.base_types \
    import NULLABLE_IP_ADDRESS
from nailgun.api.v1.validators.json_schema.base_types \
    import NULLABLE_MAC_ADDRESS
from nailgun.api.v1.validators.json_schema.base_types \
    import NULLABLE_NON_NEGATIVE_INTEGER
from nailgun.api.v1.validators.json_schema.base_types \
    import NULLABLE_POSITIVE_INTEGER
from nailgun.api.v1.validators.json_schema.base_types import NULLABLE_STRING
from nailgun.api.v1.validators.json_schema.base_types import POSITIVE_INTEGER
from nailgun.api.v1.validators.json_schema.base_types import POSITIVE_NUMBER
from nailgun.api.v1.validators.json_schema.base_types import STRINGS_ARRAY


NODE_STATUS = {
    'type': 'string',
    'enum': list(consts.NODE_STATUSES)
}

INTERFACE = {
    'type': 'object',
    'properties': {
        'ip': IP_ADDRESS,
        'mac': MAC_ADDRESS,
        'max_speed': NULLABLE_POSITIVE_INTEGER,
        'name': {'type': 'string'},
        'current_speed': NULLABLE_NON_NEGATIVE_INTEGER,
    },
    'required': ['mac', 'name']
}

DISK = {
    'type': 'object',
    'properties': {
        'model': NULLABLE_STRING,
        'disk': {'type': 'string'},
        'size': POSITIVE_INTEGER,
        'name': {'type': 'string'},
    },
    'required': ['model', 'disk', 'size', 'name']
}

MEMORY_CHIP = {
    'type': 'object',
    'properties': {
        'frequency': POSITIVE_NUMBER,
        'type': {'type': 'string'},
        'size': POSITIVE_INTEGER
    },
    'required': ['type', 'size']
}

MEMORY_BANK = {
    'type': 'object',
    'properties': {
        'slots': POSITIVE_INTEGER,
        'total': POSITIVE_INTEGER,
        'maximum_capacity': POSITIVE_INTEGER,
        'devices': {
            'type': 'array',
            'items': MEMORY_CHIP
        }
    }
}

SYSTEM = {
    'type': 'object',
    'properties': {
        'product': {'type': 'string'},
        'family': {'type': 'string'},
        'manufacturer': {'type': 'string'},
        'version': {'type': 'string'},
        'serial': {'type': 'string'},
        'fqdn': {'type': 'string'},
    }
}

CPU_UNIT = {
    'type': 'object',
    'properties': {
        'model': {'type': 'string'},
        'model_name': {'type': 'string'},
        'vendor_id': {'type': 'string'},
        'frequency': POSITIVE_NUMBER,
        'cache_size': {'type': 'string'},
        'flags': STRINGS_ARRAY,
    },
    'required': ['model', 'frequency']
}

CPU = {
    'type': 'object',
    'properties': {
        'spec': {
            'type': 'array',
            'items': CPU_UNIT
        },
        'total': POSITIVE_INTEGER,
        'real': POSITIVE_INTEGER,
    },
    'required': ['real', 'total', 'spec']
}

NETWORK = {
    'type': 'object',
    'properties': {
        'name': {'type': 'string'},
        'dev': {'type': 'string'},
        'ip': NET_ADDRESS,
        'vlan': NULLABLE_POSITIVE_INTEGER,
        'netmask': IP_ADDRESS,
        'brd': IP_ADDRESS
    },
    'required': ['name', 'dev']
}

NODE = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'title': "Node",
    'description': "Serialized Node object",
    'type': 'object',
    'properties': {
        'id': ID,
        'name': {'type': 'string'},
        'status': NODE_STATUS,
        'roles': STRINGS_ARRAY,
        'cluster': NULLABLE_ID,
        'cluster_id': NULLABLE_ID,
        'ip': NULLABLE_IP_ADDRESS,
        'error_type': NULLABLE_STRING,
        'error_msg': {'type': 'string'},
        'pending_addition': {'type': 'boolean'},
        'fqdn': NULLABLE_STRING,
        'platform_name': NULLABLE_STRING,
        'kernel_params': NULLABLE_STRING,
        'mac': NULLABLE_MAC_ADDRESS,
        'pending_deletion': {'type': 'boolean'},
        'online': {'type': 'boolean'},
        'progress': NON_NEGATIVE_INTEGER,
        'pending_roles': STRINGS_ARRAY,
        'os_platform': NULLABLE_STRING,
        'manufacturer': NULLABLE_STRING,
        'meta': {
            'type': 'object',
            'properties': {
                'interfaces': {
                    'type': 'array',
                    'items': INTERFACE
                },
                'disks': {
                    'type': 'array',
                    'items': DISK
                },
                'memory': MEMORY_BANK,
                'cpu': CPU,
                'system': SYSTEM
            }
        },
        'network_data': {
            'type': 'array',
            'items': NETWORK
        },
        'agent_checksum': {'type': 'string'}
    },
    'required': ['id', 'name', 'status', 'roles', 'ip', 'error_type',
                 'pending_addition', 'fqdn', 'platform_name', 'kernel_params',
                 'mac', 'pending_deletion', 'online', 'progress',
                 'pending_roles', 'os_platform', 'meta', 'manufacturer',
                 'network_data'],
    'additionalProperties': True
}

# GET schema
GET_REQUEST = {}

GET_RESPONSE = copy.deepcopy(NODE)

# PUT schema
PUT_REQUEST = copy.deepcopy(NODE)
PUT_REQUEST.pop('required')
PUT_REQUEST['additionalProperties'] = False

PUT_RESPONSE = GET_RESPONSE
