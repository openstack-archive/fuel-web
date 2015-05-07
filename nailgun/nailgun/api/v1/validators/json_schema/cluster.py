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

from nailgun import consts

from nailgun.api.v1.validators.json_schema import base_types
from nailgun.api.v1.validators.json_schema import role


# TODO(@ikalnitsky): add `required` properties to all needed objects
single_schema = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "Cluster",
    "description": "Serialized Cluster object",
    "type": "object",
    "properties": {
        "id": {"type": "number"},
        "name": {"type": "string"},
        "mode": {
            "type": "string",
            "enum": list(consts.CLUSTER_MODES)
        },
        "status": {
            "type": "string",
            "enum": list(consts.CLUSTER_STATUSES)
        },
        "net_provider": {
            "type": "string",
            "enum": list(consts.CLUSTER_NET_PROVIDERS)
        },
        "grouping": {
            "type": "string",
            "enum": list(consts.CLUSTER_GROUPING)
        },
        "view_mode": {
            "type": "string",
            "enum": list(consts.CLUSTER_VIEW_MODES)
        },
        "release_id": {"type": "number"},
        "pending_release_id": base_types.NULLABLE_ID,
        "replaced_deployment_info": {"type": "object"},
        "replaced_provisioning_info": {"type": "object"},
        "is_customized": {"type": "boolean"},
        "fuel_version": {"type": "string"}
    }
}

collection_schema = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "Cluster collection",
    "description": "Serialized Cluster collection",
    "type": "object",
    "items": single_schema["properties"]
}

attribute_schema = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'title': 'Schema for single editable attribute',
    'type': 'object',
    'properties': {
        'type': {
            'enum': [
                'checkbox',
                'custom_repo_configuration',
                'hidden',
                'password',
                'radio',
                'select',
                'text',
                'textarea',
            ]
        },
        #'value': None,  # custom validation depending on type
        'restrictions': role.RESTRICTIONS,
        'weight': {
            'type': 'integer',
            'minimum': 0,
        },
    },
    'required': ['type', 'value'],
}

# Schema with allowed values for 'radio' and 'select' attribute types
allowed_values_schema = {
    'value': {
        'type': 'string',
    },
    'values': {
        'type': 'array',
        'minItems': 1,
        'items': [
            {
                'type': 'object',
                'properties': {
                    'data': {'type': 'string'},
                    'label': {'type': 'string'},
                    'description': {'type': 'string'},
                    'restrictions': role.RESTRICTIONS,
                },
                'required': ['data', 'label'],
            },
        ],
    },
}

# Additional properties definitions for 'attirbute_schema'
# depending on 'type' property
attribute_type_schemas = {
    'checkbox': {'value': {'type': 'boolean'}},
    'custom_repo_configuration': {
        'value': {
            'type': 'array',
            'minItems': 1,
            'items': [
                {
                    'type': 'object',
                    'properties': {
                        'name': {'type': 'string'},
                        'priority': {'type': ['integer', 'null']},
                        'section': {'type': 'string'},
                        'suite': {'type': 'string'},
                        'type': {'type': 'string'},
                        'uri': {'type': 'string'},
                    }
                }
            ],
        },
    },
    'password': {'value': {'type': 'string'}},
    'radio': allowed_values_schema,
    'select': allowed_values_schema,
    'text': {'value': {'type': 'string'}},
    'textarea': {'value': {'type': 'string'}},
}

vmware_attributes_schema = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "Vmware attributes",
    "description": "Serialized VmwareAttributes object",
    "type": "object",
    "required": ["editable"],
    "properties": {
        "editable": {"type": "object"}
    }
}
