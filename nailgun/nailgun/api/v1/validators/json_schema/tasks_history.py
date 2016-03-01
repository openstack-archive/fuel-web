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

from nailgun.consts import TASK_STATUSES

TASKS_HISTORY_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'type': 'object',
    'properties': {
        'deployment_task_id': {'type': 'integer'},
        'node_id': {'type': 'integer'},
        'task_id': {'type': 'integer'},
        'task_name': {'type': 'string'},
        'time_start': {'type': 'integer'},
        'time_end': {'type': 'integer'},
        'status': {'enum': list(TASK_STATUSES),
                   'type': 'string'},
        'summary': 'object'}
    },
    'required': [
        'deployment_task_id',
        'node_id',
        'task_id',
        'task_name',
        'status'
    ]
}

TASKS_HISTORIES_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'type': 'array',
    'items': TASKS_HISTORY_SCHEMA}
