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


# Non-complete JSON Schema for validating IP addresses.
# Use it for better readability in the main schema.
_IP_ADDRESS_SCHEMA = {
    'type': 'string',
    'format': 'ipv4',
}

_IP_ADDRESS_OR_NULL_SCHEMA = {
    'type': ['string', 'null'],
    'format': 'ipv4',
}


# Non-complete JSON schema for validating NET addresses.
# Use it for better readability in the main schema.
_NET_ADDRESS_SCHEMA = {
    'type': 'string',

    # check for valid ip address and route prefix
    # e.g: 192.168.0.0/24
    'pattern': '^(({octet}\.){{3}}{octet})({prefix})?$'.format(
        octet='(2(5[0-5]|[0-4][0-9])|[01]?[0-9][0-9]?)',
        prefix='/(3[012]|[12]?[0-9])'
    ),
}


_NET_ADDRESS_OR_NULL_SCHEMA = {
    'type': ['string', 'null'],

    # check for valid ip address and route prefix
    # e.g: 192.168.0.0/24
    'pattern': _NET_ADDRESS_SCHEMA['pattern'],
}


# Non-complete JSON Schema for validating MAC addresses.
# Use it for better readability in the main schema.
_MAC_ADDRESS_SCHEMA = {
    'type': 'string',
    'pattern': '^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$',
}


NETWORK = {
    'type': 'object',
    'properties': {
        'name': {'type': 'string'},
        'cidr': _NET_ADDRESS_SCHEMA,
        'gateway': _IP_ADDRESS_SCHEMA,
        'ip_range': {'type': 'array'},
        'vlan_start': {'type': ['null', 'number']},
        'use_gateway': {'type': 'boolean'},
        'notation': {'type': ['string', 'null']},
        'render_type': {'type': ['null', 'string']},
        'map_priority': {'type': 'number'},
        'configurable': {'type': 'boolean'},
        'floating_range_var': {'type': 'string'},
        'ext_net_data': {'type': 'array'},
        'assign_vip': {'type': 'boolean'}},
    'required': ['name']
}
