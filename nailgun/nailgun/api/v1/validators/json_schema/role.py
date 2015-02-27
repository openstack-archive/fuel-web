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


VOLUME_ALLOCATION = {
    'type': 'object',
    'description': 'Volume allocations for role',
    'required': ['allocate_size', 'id'],
    'properties': {
        'allocate_size': {'type': 'string',
                          'enum': ['all', 'min', 'full-disk']},
        'id': {'type': 'string'}}}


VOLUME_ALLOCATIONS = {
    'type': 'array',
    "minItems": 1,
    'items': VOLUME_ALLOCATION}


ROLE_META_INFO = {
    "type": "object",
    "required": ["name"],
    "properties": {
        "name": {
            "type": "string",
            "description": "Name that will be shown on UI"},
        "description": {
            "type": "string",
            "description": "Short description of role functionality"}}}


SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "Role",
    "description": "Serialized Role object",
    "type": "object",
    "required": ['name', 'release_id', 'meta', 'volumes'],
    "properties": {
        "id": {"type": "integer"},
        "name": {"type": "string"},
        "release_id": {"type": "integer"},
        "meta": ROLE_META_INFO,
        "volumes": VOLUME_ALLOCATIONS}}
