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


# TODO(@ikalnitsky): add `required` properties to all needed objects
single_schema = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "Node",
    "description": "Serialized Node object",
    "type": "object",
    "properties": {
        "mac": base_types.MAC_ADDRESS,
        "ip": base_types.IP_ADDRESS,
        "meta": {
            "type": "object",
            "properties": {
                # I guess the format schema below will be used somewhere else,
                # so it would be great to move it out in the future.
                "interfaces": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "ip": base_types.NULLABLE_IP_ADDRESS,
                            "netmask": base_types.NET_ADDRESS,
                            "mac": base_types.MAC_ADDRESS,
                            "state": {"type": "string"},
                            "name": {"type": "string"},
                            "driver": {"type": "string"},
                            "bus_info": {"type": "string"},
                            "offloading_modes": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "state": {
                                            "type": [
                                                "boolean",
                                                "null"
                                            ]
                                        },
                                        "sub": {
                                            "$ref": "#/properties/meta/"
                                                    "properties/interfaces/"
                                                    "items/properties/"
                                                    "offloading_modes"

                                        }
                                    }
                                }
                            },
                            "pxe": {"type": "boolean"}
                        }
                    }
                },
                # I guess the format schema below will be used somewhere else,
                # so it would be great to move it out in the future.
                "disks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "model": base_types.NULLABLE_STRING,
                            "disk": {"type": "string"},
                            "size": {"type": "number"},
                            "name": {"type": "string"},
                        }
                    }
                },
                "memory": {
                    "type": "object",
                    "properties": {
                        "total": {"type": "number"}
                    }
                },
                "cpu": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "model": {"type": "string"},
                                    "frequency": {"type": "number"}
                                }
                            }
                        },
                        "total": {"type": "integer"},
                        "real": {"type": "integer"},
                    }
                },
                "system": {
                    "type": "object",
                    "properties": {
                        "manufacturer": {"type": "string"},
                        "version": {"type": "string"},
                        "serial": {"type": "string"},
                        "family": {"type": "string"},
                        "fqdn": {"type": "string"},
                    }
                },
                "numa_topology": {
                    "type": "object",
                    "properties": {
                        "supported_hugepages": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                        "numa_nodes": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer"},
                                    "cpus": {
                                        "type": "array",
                                        "items": {"type": "integer"},
                                    },
                                    "memory": {"type": "integer"},
                                },
                                "required": [
                                    "id",
                                    "cpus",
                                    "memory",
                                ]
                            }
                        },
                        "distances": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {"type": "string"},
                            }
                        }
                    },
                    "required": [
                        "supported_hugepages",
                        "numa_nodes",
                        "distances",
                    ]
                }
            }
        },
        "id": {"type": "integer"},
        "status": {"enum": list(consts.NODE_STATUSES)},
        "cluster_id": base_types.NULLABLE_ID,
        "name": {"type": "string"},
        "manufacturer": base_types.NULLABLE_STRING,
        "os_platform": base_types.NULLABLE_STRING,
        "is_agent": {"type": "boolean"},
        "platform_name": base_types.NULLABLE_STRING,
        "group_id": {"type": "number"},
        "hostname": {"type": "string"},
        "kernel_params": base_types.NULLABLE_STRING,
        "progress": {"type": "number"},
        "pending_addition": {"type": "boolean"},
        "pending_deletion": {"type": "boolean"},
        "error_type": base_types.NULLABLE_ENUM(list(consts.NODE_ERRORS)),
        "error_msg": {"type": "string"},
        "online": {"type": "boolean"},
        "labels": {
            "type": "object",
            "patternProperties": {
                "^.{1,100}$": {
                    "oneOf": [
                        {"type": "string", "maxLength": 100, "minLength": 1},
                        {"type": "null"},
                    ]
                },
            },
            "additionalProperties": False,
        },
        "roles": {"type": "array", "items": {"type": "string"}},
        "pending_roles": {"type": "array", "items": {"type": "string"}},
        "agent_checksum": {"type": "string"}
    },
}

_VDA_SIZE_RE = "^[0-9]+[bkKMGT]?$"

_VMS_CONF_SCHEMA = {
    "type": "object",
    "properties": {
        "id": base_types.POSITIVE_INTEGER,
        "mem": base_types.POSITIVE_INTEGER,
        "cpu": base_types.POSITIVE_INTEGER,
        "vda_size": {
            "type": "string",
            "pattern": _VDA_SIZE_RE,
        }
    },
    "required": ["id"],
}

NODE_VM_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "Node VM",
    "description": "Node VM object",
    "type": "object",
    "properties": {
        "vms_conf": {
            "type": "array",
            "items": _VMS_CONF_SCHEMA,
        },
    },
    "required": ["vms_conf"],
    "additionalProperties": False,
}
