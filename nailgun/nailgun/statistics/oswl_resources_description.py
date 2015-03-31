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

from nailgun.statistics import WhiteListRule


resources_description = {
    "vm": {
        "retrieved_from_component": "nova",
        "supported_api_versions": {
            "v1.1": {
                "attributes_white_list": (
                    WhiteListRule(("id",), "id", None),
                    WhiteListRule(("status",), "status", None),
                    WhiteListRule(("tenant_id",), "tenant_id", None),
                    WhiteListRule(("hostId",), "host_id", None),
                    WhiteListRule(("created",), "created_at", None),
                    WhiteListRule(("OS-EXT-STS:power_state",), "power_state",
                                  None,),
                    WhiteListRule(("flavor", "id",), "flavor_id", None),
                    WhiteListRule(("image", "id",), "image_id", None),
                ),
                "resource_manager_name": "servers",
                "additional_display_options": {
                    "search_opts": {"all_tenants": 1},
                },
            },
        },
    },
    "flavor": {
        "retrieved_from_component": "nova",
        "supported_api_versions": {
            "v1.1": {
                "attributes_white_list": (
                    WhiteListRule(("id",), "id", None),
                    WhiteListRule(("ram",), "ram", None),
                    WhiteListRule(("vcpus",), "vcpus", None),
                    WhiteListRule(("OS-FLV-EXT-DATA:ephemeral",),
                                  "ephemeral", None),
                    WhiteListRule(("disk",), "disk", None),
                    WhiteListRule(("swap",), "swap", None),
                ),
                "resource_manager_name": "flavors"
            },
        },
    },
    "image": {
        "retrieved_from_component": "nova",
        "supported_api_versions": {
            "v1.1": {
                "attributes_white_list": (
                    WhiteListRule(("id",), "id", None),
                    WhiteListRule(("minDisk",), "minDisk", None),
                    WhiteListRule(("minRam",), "minRam", None),
                    WhiteListRule(("OS-EXT-IMG-SIZE:size",), "sizeBytes",
                                  None),
                    WhiteListRule(("created",), "created_at", None),
                    WhiteListRule(("updated",), "updated_at", None),
                ),
                "resource_manager_name": "images"
            },
        }
    },
    "tenant": {
        "retrieved_from_component": "keystone",
        "supported_api_versions": {
            "v2.0": {
                "attributes_white_list": (
                    WhiteListRule(("id",), "id", None),
                    WhiteListRule(("enabled",), "enabled_flag", None),
                ),
                "resource_manager_name": "tenants"
            },
            "v3": {
                "attributes_white_list": (
                    WhiteListRule(("id",), "id", None),
                    WhiteListRule(("enabled",), "enabled_flag", None),
                ),
                "resource_manager_name": "projects"
            },
        }
    },
    "keystone_user": {
        "retrieved_from_component": "keystone",
        "supported_api_versions": {
            "v2.0": {
                "attributes_white_list": (
                    WhiteListRule(("id",), "id", None),
                    WhiteListRule(("enabled",), "enabled_flag", None),
                    WhiteListRule(("tenantId",), "tenant_id", None),
                ),
                "resource_manager_name": "users"
            },
            "v3": {
                "attributes_white_list": (
                    WhiteListRule(("id",), "id", None),
                    WhiteListRule(("enabled",), "enabled_flag", None),
                    WhiteListRule(("default_project_id",), "tenant_id", None),
                ),
                "resource_manager_name": "users"
            }
        },
    },
    "volume": {
        "retrieved_from_component": "cinder",
        "supported_api_versions": {
            "v1": {
                "attributes_white_list": (
                    WhiteListRule(("id",), "id", None),
                    WhiteListRule(("availability_zone",), "availability_zone",
                                  None),
                    WhiteListRule(("encrypted",), "encrypted_flag", None),
                    WhiteListRule(("bootable",), "bootable_flag", None),
                    WhiteListRule(("status",), "status", None),
                    WhiteListRule(("volume_type",), "volume_type", None),
                    WhiteListRule(("size",), "size", None),
                    WhiteListRule(("snapshot_id",), "snapshot_id", None),
                    WhiteListRule(("attachments",), "attachments", None),
                    WhiteListRule(("os-vol-tenant-attr:tenant_id",),
                                  "tenant_id", None),
                ),
                "resource_manager_name": "volumes",
                "additional_display_options": {
                    "search_opts": {"all_tenants": 1},
                },
            },
        }
    },
}
