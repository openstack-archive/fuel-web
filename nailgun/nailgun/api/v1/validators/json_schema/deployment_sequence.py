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

from nailgun.api.v1.validators.json_schema import deployment_graph


CREATE_SEQUENCE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "title": "Deployment Sequence structure",
    "description": "The structure of deployment sequence object",
    "required": ["release", "name", "graphs"],
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string"},
        "release": {"type": "integer"},
        "graphs": deployment_graph.SEQUENCE_OF_GRAPHS_SCHEMA
    }
}


UPDATE_SEQUENCE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "title": "Deployment Sequence structure",
    "description": "The structure of deployment sequence object",
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string"},
        "graphs": deployment_graph.SEQUENCE_OF_GRAPHS_SCHEMA
    }
}


SEQUENCE_EXECUTION_PARAMS = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "title": "Sequence execution parameters",
    "description": "The parameters of api method to execute sequence",
    "required": ["cluster"],
    "additionalProperties": False,
    "properties": {
        "cluster": {"type": "integer"},
        "dry_run": {"type": "boolean"},
        "noop_run": {"type": "boolean"},
        "force": {"type": "boolean"},
        "debug": {"type": "boolean"}
    }
}
