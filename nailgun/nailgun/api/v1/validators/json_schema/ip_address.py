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

from copy import deepcopy

from nailgun.api.v1.validators.json_schema import base_types


VIP_UPDATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 64},
        "namespace": {"type": "string", "maxLength": 64},
        "network_role": {"type": "string", "maxLength": 64},
        "node_roles": {
            "type": "array",
            "items": {"type": "string", "maxLength": 64}
        },
        "alias": {"type": "string", "maxLength": 64},
        "manual": {"type": "boolean"},
        "vendor_specific": {"type": "object"}
    }
}

VIP_SCHEMA = deepcopy(VIP_UPDATE_SCHEMA)
VIP_SCHEMA["required"] = [
    "name",
    "namespace",
    "node_roles",
]

IP_ADDRESS_UPDATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "id": {"type": "integer"},
        "network": base_types.NULLABLE_ID,
        "node": base_types.NULLABLE_ID,
        "ip_addr": base_types.IP_ADDRESS,
        "vip_info": VIP_UPDATE_SCHEMA
    }
}

IP_ADDRESS_SCHEMA = deepcopy(IP_ADDRESS_UPDATE_SCHEMA)
IP_ADDRESS_SCHEMA["required"] = ["ip_addr", ]


IP_ADDRESSES_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "array",
    "items": IP_ADDRESS_SCHEMA
}

IP_ADDRESSES_UPDATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "array",
    "items": IP_ADDRESS_UPDATE_SCHEMA
}
