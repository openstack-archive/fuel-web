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


NOVA_NETWORK_SCHEMA = {
    'type': 'object',
    'properties': {
        'networks': {
            'type': 'array',
            'items': networks.NETWORK},
        'config': {'type': 'object'}},
    'required': ['networks', 'config']
}

NEUTRON_SCHEMA = {
    'type': 'object',
    'properties': {
        'networks': {
            'type': 'array',
            'items': networks.NETWORK},
        'config': {'type': 'object'}},
    'required': ['networks', 'config']
}

NETWORKS_SCHEMA = {
    'type': 'object',
    'properties': {
        'nova_network': NOVA_NETWORK_SCHEMA,
        'neutron': NEUTRON_SCHEMA,
    },
    'required': ['nova_network', 'neutron']
}
