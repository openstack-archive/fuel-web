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

DASHBOARD_ENTRY_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'type': 'object',
    'properties': {
        'id': {'type': 'integer'},
        'title': {'type': 'string', 'maxLength': 50, 'minLength': 1},
        'url': {'type': 'string'},
        'description': {'type': 'string'}
    },
    'required': ['title', 'url'],
    'additionalProperties': False
}

DASHBOARD_ENTRIES_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'type': 'array',
    'items': DASHBOARD_ENTRY_SCHEMA}

DASHBOARD_ENTRY_UPDATE_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'type': 'object',
    'properties': {
        'title': {'type': 'string', 'maxLength': 50, 'minLength': 1},
        'url': {'type': 'string'},
        'description': {'type': 'string'}
    },
    'additionalProperties': False
}
