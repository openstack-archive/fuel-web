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

from nailgun.api.v1.validators.json_schema import base_types


INTERFACE = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "assigned_networks": {
            "type": "array"
        },
        "bus_info": base_types.NULLABLE_STRING,
        "current_speed": base_types.NULLABLE_STRING,
        "driver": base_types.NULLABLE_STRING,
        "id": base_types.POSITIVE_INTEGER,
        "interface_properties": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "disable_offloading": {"type": "boolean"},
                "mt": base_types.NULLABLE_STRING,
                "mtu": base_types.NULLABLE_POSITIVE_INTEGER
            }
        },
        "mac": base_types.MAC_ADDRESS,
        "max_speed": base_types.NULLABLE_STRING,
        "name": "eth0",
        "offloading_modes": {
            "type": "array"
        },
        "pxe": {"type": "boolean"},
        "state": base_types.NULLABLE_STRING,
        "type": {"type": "string"},
    }
}

INTERFACES = {
    "type": "array",
    "items": INTERFACE
}
