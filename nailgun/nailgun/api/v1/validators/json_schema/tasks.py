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

from nailgun.consts import ORCHESTRATOR_TASK_TYPES
from nailgun.consts import TASK_ROLES
from nailgun.consts import NODE_RESOLVE_POLICY


RELATION_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'type': 'object',
    'required': ['name'],
    'properties': {
        'name': {'type': 'string'},
        'role': {
            'oneOf': [
                {'type': 'string', 'enum': list(TASK_ROLES)},
                {'type': 'array'},
            ]
        },
        'policy': {'type': 'string', 'enum': list(NODE_RESOLVE_POLICY)},
    }
}


TASK_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'type': 'object',
    'required': ['type', 'id'],
    'properties': {
        'id': {'type': 'string'},
        'type': {'enum': list(ORCHESTRATOR_TASK_TYPES),
                 'type': 'string'},
        'version': {'type': 'string', "pattern": "^\d+.\d+.\d+$"},
        'parameters': {'type': 'object'},
        'required_for': {'type': 'array'},
        'requires': {'type': 'array'},
        'cross-depends': {'type': 'array', 'items': RELATION_SCHEMA},
        'cross-depended-by': {'type': 'array', 'items': RELATION_SCHEMA},
        'strategy': {
            'type': 'object',
            'required': ['type'],
            'properties': {
                'type': {'enum': ['parallel', 'one-by-one'],
                         'type': 'string'},
                'amount': {'type': 'integer'}
            }
        }
    }
}


TASKS_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'type': 'array',
    'items': TASK_SCHEMA}
