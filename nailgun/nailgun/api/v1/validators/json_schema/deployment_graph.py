#    Copyright 2016 Mirantis, Inc.
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

from nailgun.api.v1.validators.json_schema.tasks import TASKS_SCHEMA
from nailgun import consts


NODE_ATTRIBUTES_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'type': 'object',
    'properties': {
        # the status deleted are used for deletion node from cluster
        'status': {'enum': list(consts.NODE_STATUSES) + ['deleted']},
        'pending_addition': {'type': 'boolean'},
        'pending_deletion': {'type': 'boolean'},
        'error_msg': {'type': 'string'},
        'error_type': {'enum': list(consts.NODE_ERRORS)}}
}

EVENT_CALLBACK_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'type': 'object',
    'properties': {
        'node_attributes': NODE_ATTRIBUTES_SCHEMA
    }
}


DEPLOYMENT_GRAPH_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'type': 'object',
    'additionalProperties': False,
    'properties': {
        'name': {'type': 'string'},
        'node_filter': {'type': 'string'},
        'on_success': EVENT_CALLBACK_SCHEMA,
        'on_error': EVENT_CALLBACK_SCHEMA,
        'on_stop': EVENT_CALLBACK_SCHEMA,
        'tasks': TASKS_SCHEMA
    }
}


DEPLOYMENT_GRAPHS_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "array",
    "items": DEPLOYMENT_GRAPH_SCHEMA,
}


SEQUENCE_OF_GRAPHS_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "array",
    "minItems": 1,
    "items": {
        "type": "object",
        "required": ["type"],
        "parameters": {
            "type": {
                "type": "string"
            },
            "nodes": {
                "type": "array",
                "items": {"type": "integer"}
            },
            "tasks": {
                "type": "array",
                "items": {"type": "string"}
            }
        }
    }
}


GRAPH_EXECUTE_PARAMS_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "title": "Graph execution parameters",
    "description": "The parameters of api method to execute graphs",
    "required": ["graphs", "cluster"],
    "additionalProperties": False,
    "properties": {
        "cluster": {
            "type": "integer",
        },
        "graphs": SEQUENCE_OF_GRAPHS_SCHEMA,
        "dry_run": {
            "type": "boolean"
        },
        "noop_run": {
            "type": "boolean"
        },
        "force": {
            "type": "boolean"
        },
        "debug": {
            "type": "boolean"
        },
        "subgraphs": {
            "type": "array",
            "items": {
                "type": "object",
                "parameters": {
                    "start": {
                        "type": "string"
                    },
                    "end": {
                        "type:": "string"
                    }
                }
            }
        }
    }
}
