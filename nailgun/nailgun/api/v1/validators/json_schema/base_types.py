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

NULL = {
    'type': 'null'
}

BOOLEAN = {
    'type': 'boolean'
}

NULLABLE_STRING = {
    'type': ['string', 'null']
}

POSITIVE_INTEGER = {
    'type': 'integer',
    'minValue': 1
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
    'minValue': 0
}

NULLABLE_NON_NEGATIVE_INTEGER = {
    'anyOf': [NON_NEGATIVE_INTEGER, NULL]
}

STRINGS_ARRAY = {
    'type': 'array',
    'items': {'type': 'string'}
}

ID = POSITIVE_INTEGER

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

NULLABLE_IP_ADDRESS = {
    'anyOf': [IP_ADDRESS, NULL]
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
