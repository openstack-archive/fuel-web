# -*- coding: utf-8 -*-

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

from nailgun.api.v1.validators.json_schema import base_types


INTERFACES = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "Interface",
    "description": "Serialized Interface object",
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "ip": base_types.NULLABLE_IP_ADDRESS,
            "netmask": base_types.NET_ADDRESS,
            "mac": base_types.NULLABLE_MAC_ADDRESS,
            "state": base_types.NULLABLE_STRING,
            "name": {"type": "string"},
            "driver": base_types.NULLABLE_STRING,
            "bus_info": base_types.NULLABLE_STRING,
            "pxe": {"type": "boolean"},
            "attributes": {
                "type": "object",
                "properties": {
                    "offloading": {
                        "type": "object"},
                    "mtu": {
                        "type": "object"},
                    "sriov": {
                        "type": "object",
                        "properties": {
                            "enabled": {
                                "type": "object",
                                "properties": {
                                    "value":
                                    base_types.NULLABLE_BOOL
                                }
                            },
                            "numvfs": {
                                "type": "object",
                                "properties": {
                                    "value":
                                    base_types.NULLABLE_POSITIVE_INTEGER
                                }
                            },
                            "physnet": {
                                "type": "object",
                                "properties": {
                                    "value": {"type": "string"}
                                }
                            }
                        }
                    },
                    "dpdk": {
                        "properties": {
                            "enabled": {
                                "type": "object",
                                "properties": {
                                    "value":
                                    base_types.NULLABLE_BOOL
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
