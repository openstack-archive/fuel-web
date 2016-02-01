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


NETWORK_SCHEME = {
    "id": "network_scheme",
    "type": "object",
    "properties": {
        "transformations": {
            "id": "transformations",
            "type": "array",
        },
        "endpoints": {
            "id": "endpoints",
            "type": "array",
        },
        "roles": {
            "id": "roles",
            "type": "object"
        },
        "priority": {
            "id": "priority",
            "type": "number",
            "optional": True
        }
    },
    "required": [
        "transformations",
        "endpoints",
        "roles",
    ],
    "additionalProperties": False
}

NIC_MAPPING = {
    "id": "nic_mapping",
    "type": "object"
}

TEMPLATES_LIST = {
    "id": "templates_list",
    "type": "array",
    "items": {"type": "string"}
}

NET_ASSIGNMENT = {
    "id": "net_assignment",
    "type": "object",
    "properties": {
        "ep": {"type": "string"}
    },
    "required": [
        "ep"
    ],
    "additionalProperties": False
}

NODE_GROUP = {
    "id": "node_group",
    "type": "object",
    "properties": {
        "nic_mapping": {
            "id": "nic_mapping",
            "type": "object",
            "properties": {
                "default": NIC_MAPPING
            },
            "patternProperties": {
                ".*": NIC_MAPPING
            },
            "required": [
                "default"
            ]
        },
        "templates_for_node_role": {
            "id": "templates_for_node_role",
            "type": "object",
            "patternProperties": {
                ".*": TEMPLATES_LIST
            },
        },
        "network_assignments": {
            "id": "network_assignments",
            "type": "object",
            "patternProperties": {
                ".*": NET_ASSIGNMENT
            },
        },
        "network_scheme": {
            "id": "network_scheme",
            "type": "object",
            "patternProperties": {
                ".*": NETWORK_SCHEME
            }
        }
    },
    "required": [
        "nic_mapping",
        "templates_for_node_role",
        "network_assignments",
        "network_scheme"
    ],
    "additionalProperties": False
}


NETWORK_TEMPLATE = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "properties": {
        "adv_net_template": {
            "id": "adv_net_template",
            "type": "object",
            "patternProperties": {
                ".*": NODE_GROUP
            }
        }
    },
    "required": [
        "adv_net_template"
    ],
    "additionalProperties": False
}
