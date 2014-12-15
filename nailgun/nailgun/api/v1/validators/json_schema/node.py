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
        "meta": {"type": "object"},
        "fqdn": base_types.NULLABLE_STRING,
        "kernel_params": base_types.NULLABLE_STRING,
        "progress": {"type": "number"},
        "pending_addition": {"type": "boolean"},
        "pending_deletion": {"type": "boolean"},
        "error_type": base_types.NULLABLE_ENUM(list(consts.NODE_ERRORS)),
        "error_msg": {"type": "string"},
        "online": {"type": "boolean"},
        "roles": {"type": "array"},
        "pending_roles": {"type": "array"},
        "agent_checksum": {"type": "string"}
    },
}
