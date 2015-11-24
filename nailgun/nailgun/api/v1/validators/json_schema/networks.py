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

from nailgun.api.v1.validators.json_schema import base_types
from nailgun.api.v1.validators.json_schema import network_template
from nailgun import consts

NETWORK_META = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string"},
        "cidr": base_types.NULLABLE_NET_ADDRESS,
        "gateway": base_types.NULLABLE_IP_ADDRESS,
        "ip_range": base_types.IP_ADDRESS_RANGE,
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
        },
        "restrictions": base_types.RESTRICTIONS
    }
}

_NETWORK_GROUP = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "NetworkGroup",
    "description": "Serialized NetworkGroup object",
    "type": "object",
    "required": ["id"],
    "additionalProperties": False,
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
            "items": base_types.IP_ADDRESS_RANGE,
        },
        "meta": NETWORK_META
    }
}

NETWORK_GROUPS = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "required": ["networks"],
    "properties": {
        "networks": {
            "type": "array",
            "items": _NETWORK_GROUP
        }
    }
}

NOVA_NETWORK_CONFIGURATION = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "properties": {
        "networking_parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "dns_nameservers": base_types.IP_ADDRESS_LIST,
                "fixed_network_size": base_types.NON_NEGATIVE_INTEGER,
                "fixed_networks_amount": base_types.NON_NEGATIVE_INTEGER,
                "fixed_networks_cidr": base_types.NET_ADDRESS,
                "fixed_networks_vlan_start":
                    base_types.NULLABLE_NON_NEGATIVE_INTEGER,
                "net_manager": {
                    "enum": list(consts.NOVA_NET_MANAGERS)
                },
                "floating_ranges": {
                    "type": "array",
                    "items": base_types.IP_ADDRESS_RANGE
                }
            }
        }
    }
}

NEUTRON_NETWORK_CONFIGURATION = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "properties": {
        "networking_parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "base_mac": base_types.MAC_ADDRESS,
                "configuration_template": {
                    "anyOf": [
                        network_template.NETWORK_TEMPLATE,
                        base_types.NULL
                    ]
                },
                "dns_nameservers": base_types.IP_ADDRESS_LIST,
                "floating_name": {"type": "string"},
                "floating_ranges": {
                    "type": "array",
                    "items": base_types.IP_ADDRESS_RANGE
                },
                "gre_id_range": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 2,
                    "uniqueItems": True,
                    "items": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 65535,
                        "exclusiveMinimum": False,
                        "exclusiveMaximum": False
                    },
                },
                "internal_name": {"type": "string"},
                "internal_cidr": base_types.NULLABLE_NET_ADDRESS,
                "internal_gateway": base_types.NULLABLE_IP_ADDRESS,
                "net_l23_provider": {
                    "enum": list(consts.NEUTRON_L23_PROVIDERS)
                },
                "segmentation_type": {
                    "enum": list(consts.NEUTRON_SEGMENT_TYPES)
                },
                "vlan_range": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 2,
                    "uniqueItems": True,
                    "items": {
                        "type": "integer",
                        "minimum": 2,
                        "maximum": 4094,
                        "exclusiveMinimum": False,
                        "exclusiveMaximum": False
                    }
                },
                "baremetal_gateway": base_types.NULLABLE_IP_ADDRESS,
                "baremetal_range": base_types.NULLABLE_IP_ADDRESS_RANGE,
            },
            "dependencies": {
                "baremetal_range": ["baremetal_gateway"]
            }
        }
    }
}


VIP_INFO = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "required": ["name"],
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string"},
        "network_role": {"type": "string"},
        "namespace": {"type": "string"},
        "node_roles": {"type": "string"},
        "alias": {"type": "string"},
        "manual": {"type": "boolean"},
    }
}
