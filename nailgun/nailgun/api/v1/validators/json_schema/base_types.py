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

# Common json schema types definition

from nailgun import consts

NULL = {
    'type': 'null'
}

NULLABLE_STRING = {
    'type': ['string', 'null']
}

NULLABLE_BOOL = {
    'type': ['boolean', 'null']
}

POSITIVE_INTEGER = {
    'type': 'integer',
    'minimum': 1
}

POSITIVE_NUMBER = {
    'type': 'number',
    'minimum': 0,
    'exclusiveMinimum': True
}

NULLABLE_POSITIVE_INTEGER = {
    'anyOf': [POSITIVE_INTEGER, NULL]
}

NULLABLE_ENUM = lambda e: {
    "enum": e + [None]
}

NON_NEGATIVE_INTEGER = {
    'type': 'integer',
    'minimum': 0
}

NULLABLE_NON_NEGATIVE_INTEGER = {
    'anyOf': [NON_NEGATIVE_INTEGER, NULL]
}

ID = POSITIVE_INTEGER

IDS_ARRAY = {
    'type': 'array',
    'items': ID,
}

STRINGS_ARRAY = {
    'type': 'array',
    'items': {'type': 'string'}
}

NULLABLE_ID = {
    'anyOf': [ID, NULL]
}

IP_ADDRESS = {
    'type': 'string',
    'anyOf': [
        {'format': 'ipv4'},
        {'format': 'ipv6'},
    ]
}

IP_ADDRESS_RANGE = {
    "type": "array",
    "minItems": 2,
    "maxItems": 2,
    "items": IP_ADDRESS
}

IP_ADDRESS_LIST = {
    "type": "array",
    "minItems": 1,
    "uniqueItems": True,
    "items": IP_ADDRESS
}

NULLABLE_IP_ADDRESS = {
    'anyOf': [IP_ADDRESS, NULL]
}

NULLABLE_IP_ADDRESS_RANGE = {
    'anyOf': [IP_ADDRESS_RANGE, NULL]
}

NET_ADDRESS = {
    'type': 'string',
    # check for valid ip address and route prefix
    # e.g: 192.168.0.0/24
    'pattern': '^(({octet}\.){{3}}{octet})({prefix})?$'.format(
        octet='(2(5[0-5]|[0-4][0-9])|[01]?[0-9][0-9]?)',
        prefix='/(3[012]|[12]?[0-9])'
    ),
}

NULLABLE_NET_ADDRESS = {
    'anyOf': [NET_ADDRESS, NULL]
}

MAC_ADDRESS = {
    'type': 'string',
    'pattern': '^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$',
}

NULLABLE_MAC_ADDRESS = {
    'anyOf': [MAC_ADDRESS, NULL]
}

FQDN = {
    'type': 'string',
    'pattern': '^({label}\.)*{label}$'.format(
        label='[a-zA-Z0-9]([a-zA-Z0-9\\-]{0,61}[a-zA-Z0-9])?'
    )
}

ERROR_RESPONSE = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'title': 'Error response',
    'type': 'object',
    'properties': {
        'error_code': {'type': 'string'},
        'message': {'type': 'string'}
    },
    'required': ['error_code', 'message']
}

_FULL_RESTRICTION = {
    "type": "object",
    "required": ["condition"],
    "properties": {
        "condition": {"type": "string"},
        "message": {"type": "string"},
        "action": {"type": "string"}}}


# restriction can be specified as one item dict, with condition as a key
# and value as a message
_SHORT_RESTRICTION = {
    "type": "object",
    "minProperties": 1,
    "maxProperties": 1}

RESTRICTIONS = {
    "type": "array",
    "minItems": 1,
    "items": {"anyOf": [{"type": "string"}, _FULL_RESTRICTION,
                        _SHORT_RESTRICTION]}
}

UI_SETTINGS = {
    "type": "object",
    "required": [
        "view_mode",
        "filter",
        "sort",
        "filter_by_labels",
        "sort_by_labels",
        "search"
    ],
    "additionalProperties": False,
    "properties": {
        "view_mode": {
            "type": "string",
            "description": "View mode of cluster nodes",
            "enum": list(consts.NODE_VIEW_MODES),
        },
        "filter": {
            "type": "object",
            "description": ("Filters applied to node list and "
                            "based on node attributes"),
            "properties": dict(
                (key, {"type": "array"}) for key in consts.NODE_LIST_FILTERS
            ),
        },
        "sort": {
            "type": "array",
            "description": ("Sorters applied to node list and "
                            "based on node attributes"),
            # TODO(@jkirnosova): describe fixed list of possible node sorters
            "items": [
                {"type": "object"},
            ],
        },
        "filter_by_labels": {
            "type": "object",
            "description": ("Filters applied to node list and "
                            "based on node custom labels"),
        },
        "sort_by_labels": {
            "type": "array",
            "description": ("Sorters applied to node list and "
                            "based on node custom labels"),
            "items": [
                {"type": "object"},
            ],
        },
        "search": {
            "type": "string",
            "description": "Search value applied to node list",
        },
    }
}


ATTRIBUTE_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'title': 'Schema for single editable attribute',
    'type': 'object',
    'properties': {
        'type': {
            'enum': [
                'checkbox',
                'custom_repo_configuration',
                'hidden',
                'password',
                'radio',
                'select',
                'text',
                'textarea',
                'file',
                'text_list',
                'textarea_list',
                'custom_hugepages',
                'simple_hugepages'
            ]
        },
        # 'value': None,  # custom validation depending on type
        'restrictions': RESTRICTIONS,
        'weight': {
            'type': 'integer',
            'minimum': 0,
        },
    },
    'required': ['type', 'value'],
}

# Schema with allowed values for 'radio' and 'select' attribute types
ALLOWED_VALUES_SCHEMA = {
    'value': {
        'type': 'string',
    },
    'values': {
        'type': 'array',
        'minItems': 1,
        'items': [
            {
                'type': 'object',
                'properties': {
                    'data': {'type': 'string'},
                    'label': {'type': 'string'},
                    'description': {'type': 'string'},
                    'restrictions': RESTRICTIONS,
                },
                'required': ['data', 'label'],
            },
        ],
    },
}

# Schema with a structure of multiple text fields setting value
MULTIPLE_TEXT_FIELDS_SCHEMA = {
    'value': {
        'type': 'array',
        'minItems': 1,
        'items': {'type': 'string'},
    },
    'min': {
        'type': 'integer',
        'minimum': 1,
    },
    'max': {
        'type': 'integer',
        'minimum': 1,
    }
}

# Additional properties definitions for 'attirbute_schema'
# depending on 'type' property
ATTRIBUTE_TYPE_SCHEMAS = {
    'checkbox': {'value': {'type': 'boolean'}},
    'custom_repo_configuration': {
        'value': {
            'type': 'array',
            'minItems': 1,
            'items': [
                {
                    'type': 'object',
                    'properties': {
                        'name': {'type': 'string'},
                        'priority': {'type': ['integer', 'null']},
                        'section': {'type': 'string'},
                        'suite': {'type': 'string'},
                        'type': {'type': 'string'},
                        'uri': {'type': 'string'},
                    }
                }
            ],
        },
    },
    'password': {'value': {'type': 'string'}},
    'radio': ALLOWED_VALUES_SCHEMA,
    'select': ALLOWED_VALUES_SCHEMA,
    'text': {'value': {'type': 'string'}},
    'simple_hugepages': {'value': {'type': ['string', 'integer']}},
    'textarea': {'value': {'type': 'string'}},
    'text_list': MULTIPLE_TEXT_FIELDS_SCHEMA,
    'textarea_list': MULTIPLE_TEXT_FIELDS_SCHEMA
}
