# Copyright 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import jsonschema

from fuel_agent import errors


KS_SPACES_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'title': 'Partition scheme',
    'type': 'array',
    'minItems': 1,
    'uniqueItems': True,
    'items': {
        'anyOf': [
            {
                'type': 'object',
                'required': ['type', 'id', 'volumes', 'name',
                             'size', 'extra', 'free_space'],
                'properties': {
                    'type': {'enum': ['disk']},
                    'id': {'type': 'string'},
                    'name': {'type': 'string'},
                    'size': {'type': 'integer'},
                    'free_space': {'type': 'integer'},
                    'extra': {
                        'type': 'array',
                        'items': {'type': 'string'},
                    },
                    'volumes': {
                        'type': 'array',
                        'items': {
                            'anyOf': [
                                {
                                    'type': 'object',
                                    'required': ['type', 'size',
                                                 'lvm_meta_size', 'vg'],
                                    'properties': {
                                        'type': {'enum': ['pv']},
                                        'size': {'type': 'integer'},
                                        'lvm_meta_size': {'type': 'integer'},
                                        'vg': {'type': 'string'}
                                    }
                                },
                                {
                                    'type': 'object',
                                    'required': ['type', 'size'],
                                    'properties': {
                                        'type': {'enum': ['raid',
                                                          'partition']},
                                        'size': {'type': 'integer'},
                                        'mount': {'type': 'string'},
                                        'file_system': {'type': 'string'},
                                        'name': {'type': 'string'}
                                    }
                                },
                                {
                                    'type': 'object',
                                    'required': ['type', 'size'],
                                    'properties': {
                                        'type': {'enum': ['boot']},
                                        'size': {'type': 'integer'}
                                    }
                                },
                                {
                                    'type': 'object',
                                    'required': ['type', 'size'],
                                    'properties': {
                                        'type': {'enum': ['lvm_meta_pool']},
                                        'size': {'type': 'integer'}
                                    }
                                },

                            ]
                        }
                    }
                }
            },
            {
                'type': 'object',
                'required': ['type', 'id', 'volumes'],
                'properties': {
                    'type': {'enum': ['vg']},
                    'id': {'type': 'string'},
                    'label': {'type': 'string'},
                    'min_size': {'type': 'integer'},
                    '_allocate_size': {'type': 'string'},
                    'volumes': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'required': ['type', 'size', 'name'],
                            'properties': {
                                'type': {'enum': ['lv']},
                                'size': {'type': 'integer'},
                                'name': {'type': 'string'},
                                'mount': {'type': 'string'},
                                'file_system': {'type': 'string'},
                            }
                        }
                    }
                }
            }
        ]
    }
}


def validate(scheme):
    """Validates a given partition scheme using jsonschema.

    :param scheme: partition scheme to validate
    """
    try:
        checker = jsonschema.FormatChecker()
        jsonschema.validate(scheme, KS_SPACES_SCHEMA,
                            format_checker=checker)
    except Exception as exc:
        raise errors.WrongPartitionSchemeError(str(exc))

    # scheme is not valid if the number of disks is 0
    if not [d for d in scheme if d['type'] == 'disk']:
        raise errors.WrongPartitionSchemeError(
            'Partition scheme seems empty')

    for space in scheme:
        for volume in space.get('volumes', []):
            if volume['size'] > 16777216 and volume['mount'] == '/':
                raise errors.WrongPartitionSchemeError(
                    'Root file system must be less than 16T')

    # TODO(kozhukalov): need to have additional logical verifications
    # maybe sizes and format of string values
