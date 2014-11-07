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


PLUGIN_RELEASE_SCHEMA = {
    'type': 'object',
    'properties': {
        'repository_path': {'type': 'string'},
        'version': {'type': 'string'},
        'os': {'type': 'string'},
        'deployment_scripts_path': {'type': 'string'},
        'mode': {
            'type': 'array',
            'items': {'type': 'string'}}
    },
    'required': ['version', 'os', 'mode']
}

PLUGIN_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'title': 'plugin',
    'type': 'object',
    'properties': {
        'id': {'type': 'integer'},
        'name': {'type': 'string'},
        'title': {'type': 'string'},
        'version': {'type': 'string'},
        'package_version': {'type': 'string'},
        'description': {'type': 'string'},
        'fuel_version': {'type': 'array',
                         'items': {'type': 'string'}},
        'releases': {
            'type': 'array',
            'items': PLUGIN_RELEASE_SCHEMA}
    },
    'required': [
        'name',
        'title',
        'version',
        'releases',
        'package_version',
        'fuel_version']
}


TASK_SCHEMA = {
    'type': 'object',
    'properties': {
        'type': {'type': 'string'},
        'parameters': {'type': 'object'},
        'stage': {'type': 'string'},
        'role': {
            'type': 'object',
            'oneOf': [
                {'type': 'array', 'items': 'string'},
                {'type': 'string'}]
        }
    }
}
