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

# Non-complete JSON Schema for validating IP addresses.
# Use it for better readability in the main schema.
_IP_ADDRESS_SCHEMA = {
    'type': 'string',
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


# Non-complete JSON Schema for validating MAC addresses.
# Use it for better readability in the main schema.
_MAC_ADDRESS_SCHEMA = {
    'type': 'string',
    'pattern': '^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$',
}


# TODO(@ikalnitsky): add `required` properties to all needed objects
node_format_schema = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'title': 'JSONized Node object',
    'description': 'Object with node description',
    'type': 'object',
    'properties': {
        'mac': _MAC_ADDRESS_SCHEMA,
        'ip': _IP_ADDRESS_SCHEMA,
        'meta': {
            'type': 'object',
            'properties': {
                # I guess the format schema below will be used somewhere else,
                # so it would be great to move it out in the future.
                'interfaces': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'ip': _IP_ADDRESS_SCHEMA,
                            'netmask': _NET_ADDRESS_SCHEMA,
                            'mac': _MAC_ADDRESS_SCHEMA,
                            'state': {'type': 'string'},
                            'name': {'type': 'string'},
                        }
                    }
                },
                # I guess the format schema below will be used somewhere else,
                # so it would be great to move it out in the future.
                'disks': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'model': {'type': 'string'},
                            'disk': {'type': 'string'},
                            'size': {'type': 'number'},
                            'name': {'type': 'string'},
                        }
                    }
                },
                'memory': {
                    'type': 'object',
                    'properties': {
                        'total': {'type': 'number'}
                    }
                },
                'cpu': {
                    'type': 'object',
                    'properties': {
                        'spec': {
                            'type': 'array',
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'model': {'type': 'string'},
                                    'frequency': {'type': 'number'}
                                }
                            }
                        },
                        'total': {'type': 'integer'},
                        'real': {'type': 'integer'},
                    }
                },
                'system': {
                    'type': 'object',
                    'properties': {
                        'manufacturer': {'type': 'string'},
                        'version': {'type': 'string'},
                        'serial': {'type': 'string'},
                        'family': {'type': 'string'},
                        'fqdn': {'type': 'string'},
                    }
                },
            }
        },
        'id': {'type': 'string'},
        'manufacturer': {'type': 'string'},
        'os_platform': {'type': 'string'},
        'is_agent': {'type': 'boolean'},
        'platform_name': {'type': ['string', 'null']},
    },
}
