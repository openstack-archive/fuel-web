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

from nailgun.api.v1.validators.json_schema import base_types


NETWORK = {
    'type': 'object',
    'properties': {
        'name': {'type': 'string'},
        'cidr': base_types.NET_ADDRESS,
        'gateway': base_types.IP_ADDRESS,
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
