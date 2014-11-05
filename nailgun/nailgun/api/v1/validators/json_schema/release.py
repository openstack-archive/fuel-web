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

"""
- name: "public"
            cidr: "172.16.0.0/24"
            ip_range: ["172.16.0.2", "172.16.0.126"]
            vlan_start: null
            use_gateway: true
            notation: "ip_ranges"
            render_type: null
            render_addr_mask: "public"
            map_priority: 1
            configurable: true
            floating_range_var: "floating_ranges"
            assign_vip: true
"""

NETWORK = {
    'type': 'object',
    'properties': {
        'name': {'type': 'string'},
        'ip_range': {'type': 'array',
                     'items': {'type': 'ipv4'}},
        'cidr': {'type': 'cidr'},
        'vlan_start': {'type': ['number', 'null']},
        'use_gateway': {'type': 'boolean'},
        'render_type': {'type': ['string', 'null']},
        'map_priority': {'type': 'number'},
        'configurable': {'type': 'boolean'},
        'floating_range_var': {'type': 'string'},
        'assign_vip': {'type': 'bool'}},
    'required': ['name', 'cidr', 'use_gateway']
}

NOVA_NETWORK_SCHEMA = {
    'type': 'object',
    'properties': {
        'networks': {
            'type': 'array',
            'items': NETWORK},
        'config': {'type': 'object'}},
    'required': ['networks', 'config']
}

NEUTRON_SCHEMA = {
    'type': 'object',
    'properties': {
        'networks': {
            'type': 'array',
            'items': NETWORK},
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
