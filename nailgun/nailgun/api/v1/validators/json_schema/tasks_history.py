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

TASKS_HISTORY_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'type': 'object',
    'properties': {
        'id': {'type': 'integer'},
        'deployment_task_id': {'type': 'integer'},
        'node_id': {'type': 'integer'},
        'task_name': {'type': 'string'},
        'time_started': {'type': 'string'},
        'time_ended': {'type': 'string'},
        #TODO(vsharshov): add enum of task status here
        'status': {'type': 'string'}
    },
    'required': ['title', 'url']
}

TASKS_HISTORIES_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'type': 'array',
    'items': TASKS_HISTORY_SCHEMA}

TASKS_HISTORY_UPDATE_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'type': 'object',
    #TODO(vsharshov): add enum of task status here
    'properties': {
        'status': {'type': 'string'}
    }
}