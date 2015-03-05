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


from nailgun.api.v1.validators.json_schema.base_types import POSITIVE_INTEGER


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


RESTRICTION = {
    "type": "object",
    "required": ["condition"],
    "properties": {
        "condition": {"type": "string"},
        "message": {"type": "string"},
        "action": {"type": "string"}}}


RESTRICTIONS = {
    "type": "array",
    "minItems": 1,
    "items": RESTRICTION}


OVERRIDE = {
    "type": "object",
    "required": ["condition"],
    "properties": {
        "condition": {"type": "string"},
        "max": POSITIVE_INTEGER,
        "recommended": POSITIVE_INTEGER,
        "min": POSITIVE_INTEGER,
        "message": {"type": "string"}}}


OVERRIDES = {
    "type": "array",
    "minItems": 1,
    "items": OVERRIDE}


LIMITS = {
    "type": "object",
    "properties": {
        "condition": {'type': 'string'},
        "max": POSITIVE_INTEGER,
        "recommended": POSITIVE_INTEGER,
        "min": POSITIVE_INTEGER,
        "overrides": OVERRIDES}}


ROLE_META_INFO = {
    "type": "object",
    "required": ["name", "description"],
    "properties": {
        "name": {
            "type": "string",
            "description": "Name that will be shown on UI"},
        "description": {
            "type": "string",
            "description": "Short description of role functionality"},
        "conflicts": {
            "type": "array",
            "description": "Specify which roles conflict this one."},
        "has_primary": {
            "type": "boolean",
            "description": ("During orchestration this role"
                            " will be splitted into primary-role and role.")},
        "update_required": {
            "type": "array",
            "description": ("Specified roles will be selected for deployment,"
                            " when a current role is selected.")},
        "update_once": {
            "type": "array",
            "description": ("Specified roles will be updated if current role"
                            " added to cluster first time.")},
        "limits": LIMITS,
        "restrictions": RESTRICTIONS}}


SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "Role",
    "description": "Serialized Role object",
    "type": "object",
    "required": ['name', 'meta', 'volumes_roles_mapping'],
    "properties": {
        "id": {"type": "integer"},
        "name": {"type": "string", "pattern": "^[a-zA-Z_-]+$"},
        "meta": ROLE_META_INFO,
        "volumes_roles_mapping": VOLUME_ALLOCATIONS}}
