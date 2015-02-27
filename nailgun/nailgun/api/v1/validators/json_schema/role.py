# -*- coding: utf-8 -*-
#    Copyright 2015 Mirantis, Inc.
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


VOLUME_ALLOCATIONS = {
    'type': 'array',
    "minItems": 1,
    'items': VOLUME_ALLOCATION}


VOLUME_ALLOCATION =  {
    'type': 'object',
    'description':
        'Volume allocations for role. Check openstack.yaml for examples',
    'properties': {
        'allocate_size': {
            'type': {'enum': ['all', 'min', 'full-disk']}},
            'id': {'type': 'string'}}}


SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "Role",
    "description": "Serialized Role object",
    "type": "object",
    "properties": {
        "id": {
            "type": "string",
            "description": "Unique identifier of role across release"},
        "name": {
            "type": "string",
            "description": "Name that will be shown on UI"},
        "description": {
            "type": "string",
            "description": "Short description of role functionality"},
        "volumes": VOLUME_ALLOCATIONS}

