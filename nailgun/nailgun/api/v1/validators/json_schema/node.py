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

from nailgun.api.v1.validators.json_schema import networks
from nailgun import consts


# TODO(@ikalnitsky): add `required` properties to all needed objects
node_format_schema = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'title': 'JSONized Node object',
    'description': 'Object with node description',
    'type': 'object',
    'properties': {
        'mac': networks._MAC_ADDRESS_SCHEMA,
        'ip': networks._IP_ADDRESS_SCHEMA,
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
                            'ip': networks._IP_ADDRESS_OR_NULL_SCHEMA,
                            'netmask': networks._NET_ADDRESS_OR_NULL_SCHEMA,
                            'mac': networks._MAC_ADDRESS_SCHEMA,
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
                            'model': {'type': ['string', 'null']},
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
        'status': {'enum': list(consts.NODE_STATUSES)},
        'id': {'type': ['string', 'integer']},
        'manufacturer': {'type': ['string', 'null']},
        'os_platform': {'type': ['string', 'null']},
        'is_agent': {'type': 'boolean'},
        'platform_name': {'type': ['string', 'null']},
    },
}
