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


resources_description = {
    "vm": {
        "retrieved_from_component": "nova",
        "supported_api_versions": {
            "v1.1": {
                "retrieved_attr_names_mapping": {
                    "id": ["id"],
                    "status": ["status"],
                    "tenant_id": ["tenant_id"],
                    "host_id": ["hostId"],
                    "created_at": ["created"],
                    "power_state": ["OS-EXT-STS:power_state"],
                    "flavor_id": ["flavor", "id"],
                    "image_id": ["image", "id"],
                },
                "resource_manager_name": "servers"
            },
        },
    },
    "flavor": {
        "retrieved_from_component": "nova",
        "supported_api_versions": {
            "v1.1": {
                "retrieved_attr_names_mapping": {
                    "id": ["id"],
                    "ram": ["ram"],
                    "vcpus": ["vcpus"],
                    "ephemeral": ["OS-FLV-EXT-DATA:ephemeral"],
                    "disk": ["disk"],
                    "swap": ["swap"],
                },
                "resource_manager_name": "flavors"
            },
        },
    },
    "image": {
        "retrieved_from_component": "nova",
        "supported_api_versions": {
            "v1.1": {
                "retrieved_attr_names_mapping": {
                    "id": ["id"],
                    "minDisk": ["minDisk"],
                    "minRam": ["minRam"],
                    "sizeBytes": ["OS-EXT-IMG-SIZE:size"],
                    "created_at": ["created"],
                    "updated_at": ["updated"]
                },
                "resource_manager_name": "images"
            },
        }
    },
    "tenant": {
        "retrieved_from_component": "keystone",
        "supported_api_versions": {
            "v2.0": {
                "retrieved_attr_names_mapping": {
                    "id": ["id"],
                    "enabled_flag": ["enabled"],
                },
                "resource_manager_name": "tenants"
            },
            "v3": {
                "retrieved_attr_names_mapping": {
                    "id": ["id"],
                    "enabled_flag": ["enabled"],
                },
                "resource_manager_name": "projects"
            },
        }
    },
    "keystone_user": {
        "retrieved_from_component": "keystone",
        "supported_api_versions": {
            "v2.0": {
                "retrieved_attr_names_mapping": {
                    "id": ["id"],
                    "enabled_flag": ["enabled"],
                    "tenant_id": ["tenantId"],
                },
                "resource_manager_name": "users"
            },
            "v3": {
                "retrieved_attr_names_mapping": {
                    "id": ["id"],
                    "enabled_flag": ["enabled"],
                    "tenant_id": ["default_project_id"],
                },
                "resource_manager_name": "users"
            }
        },
    },
    "volume": {
        "retrieved_from_component": "cinder",
        "supported_api_versions": {
            "v1": {
                "retrieved_attr_names_mapping": {
                    "id": ["id"],
                    "availability_zone": ["availability_zone"],
                    "encrypted_flag": ["encrypted"],
                    "bootable_flag": ["bootable"],
                    "status": ["status"],
                    "volume_type": ["volume_type"],
                    "size": ["size"],
                    "host": ["os-vol-host-attr:host"],
                    "snapshot_id": ["snapshot_id"],
                    "attachments": ["attachments"],
                    "tenant_id": ["os-vol-tenant-attr:tenant_id"],
                },
                "resource_manager_name": "volumes"
            },
        }
    },
}
