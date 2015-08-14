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

import copy

from nailgun.api.v1.validators.json_schema import base_types
from nailgun import consts

IP_RANGE = {
    "type": "array",
    "minItems": 2,
    "maxItems": 2,
    "uniqueItems": True,
    "items": {
        "type": "string",
        'anyOf': [
            {'format': 'ipv4'},
            {'format': 'ipv6'},
        ]
    }
}

NETWORK = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "cidr": base_types.NULLABLE_NET_ADDRESS,
        "gateway": base_types.NULLABLE_IP_ADDRESS,
        "ip_range": IP_RANGE,
        "vlan_start": base_types.NULLABLE_NON_NEGATIVE_INTEGER,
        "seg_type": {
            "type": "string",
            "enum": list(consts.NEUTRON_SEGMENT_TYPES),
        },
        "neutron_vlan_range": {"type": "boolean"},
        "use_gateway": {"type": "boolean"},
        "notation": base_types.NULLABLE_ENUM(
            [consts.NETWORK_NOTATION.cidr, consts.NETWORK_NOTATION.ip_ranges]
        ),
        "render_type": base_types.NULLABLE_STRING,
        "render_addr_mask": base_types.NULLABLE_STRING,
        "unmovable": {"type": "boolean"},
        "map_priority": {"type": "integer"},
        "configurable": {"type": "boolean"},
        "floating_range_var": {"type": "string"},
        "ext_net_data": {"type": "array"},
        "vips": {
            "type": "array",
            "uniqueItems": True,
            "items": {"type": "string", "pattern": "^[a-zA-Z_]+$"}
        }
    },
    "additionalProperties": False
}

NETWORK_GROUP = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "properties": {
        "networks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "group_id": base_types.NULLABLE_ID,
                    "name": {"type": "string"},
                    "release": base_types.NULLABLE_ID,
                    "gateway": base_types.NULLABLE_IP_ADDRESS,
                    "cidr": base_types.NULLABLE_NET_ADDRESS,
                    "vlan_start": base_types.NULLABLE_NON_NEGATIVE_INTEGER,
                    "ip_ranges": {
                        "type": "array",
                        "items": IP_RANGE
                    },
                    "meta": NETWORK
                },
                "required": ["id"],
                "additionalProperties": False
            }
        }
    }
}

NETWORKS = copy.copy(NETWORK_GROUP)
NETWORKS["required"] = ["networks"]
