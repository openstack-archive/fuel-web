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
                "collected_attributes": {
                    "id": {
                        "path_to_attr_on_instance": ["id"],
                    },
                    "status": {
                        "path_to_attr_on_instance": ["status"],
                    },
                    "tenant_id": {
                        "path_to_attr_on_instance": ["tenant_id"],
                    },
                    "host_id": {
                        "path_to_attr_on_instance": ["hostId"],
                    },
                    "created_at": {
                        "path_to_attr_on_instance": ["created"],
                    },
                    "power_state": {
                        "path_to_attr_on_instance": ["OS-EXT-STS:power_state"],
                    },
                    "flavor_id": {
                        "path_to_attr_on_instance": ["flavor", "id"],
                    },
                    "image_id": {
                        "path_to_attr_on_instance": ["image", "id"],
                    },
                },
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
                "collected_attributes": {
                    "id": {
                        "path_to_attr_on_instance": ["id"],
                    },
                    "ram": {
                        "path_to_attr_on_instance": ["ram"],
                    },
                    "vcpus": {
                        "path_to_attr_on_instance": ["vcpus"],
                    },
                    "ephemeral": {
                        "path_to_attr_on_instance":
                        ["OS-FLV-EXT-DATA:ephemeral"],
                    },
                    "disk": {
                        "path_to_attr_on_instance": ["disk"],
                    },
                    "swap": {
                        "path_to_attr_on_instance": ["swap"],
                    },
                },
                "resource_manager_name": "flavors"
            },
        },
    },
    "image": {
        "retrieved_from_component": "nova",
        "supported_api_versions": {
            "v1.1": {
                "collected_attributes": {
                    "id": {
                        "path_to_attr_on_instance": ["id"],
                    },
                    "minDisk": {
                        "path_to_attr_on_instance": ["minDisk"],
                    },
                    "minRam": {
                        "path_to_attr_on_instance": ["minRam"],
                    },
                    "sizeBytes": {
                        "path_to_attr_on_instance": ["OS-EXT-IMG-SIZE:size"],
                    },
                    "created_at": {
                        "path_to_attr_on_instance": ["created"],
                    },
                    "updated_at": {
                        "path_to_attr_on_instance": ["updated"]
                    },
                },
                "resource_manager_name": "images"
            },
        }
    },
    "tenant": {
        "retrieved_from_component": "keystone",
        "supported_api_versions": {
            "v2.0": {
                "collected_attributes": {
                    "id": {
                        "path_to_attr_on_instance": ["id"],
                    },
                    "enabled_flag": {
                        "path_to_attr_on_instance": ["enabled"],
                    },
                },
                "resource_manager_name": "tenants"
            },
            "v3": {
                "collected_attributes": {
                    "id": {
                        "path_to_attr_on_instance": ["id"],
                    },
                    "enabled_flag": {
                        "path_to_attr_on_instance": ["enabled"],
                    },
                },
                "resource_manager_name": "projects"
            },
        }
    },
    "keystone_user": {
        "retrieved_from_component": "keystone",
        "supported_api_versions": {
            "v2.0": {
                "collected_attributes": {
                    "id": {
                        "path_to_attr_on_instance": ["id"],
                    },
                    "enabled_flag": {
                        "path_to_attr_on_instance": ["enabled"],
                    },
                    "tenant_id": {
                        "path_to_attr_on_instance": ["tenantId"],
                    },
                },
                "resource_manager_name": "users"
            },
            "v3": {
                "collected_attributes": {
                    "id": {
                        "path_to_attr_on_instance": ["id"],
                    },
                    "enabled_flag": {
                        "path_to_attr_on_instance": ["enabled"],
                    },
                    "tenant_id": {
                        "path_to_attr_on_instance": ["default_project_id"],
                    },
                },
                "resource_manager_name": "users"
            }
        },
    },
    "volume": {
        "retrieved_from_component": "cinder",
        "supported_api_versions": {
            "v1": {
                "collected_attributes": {
                    "id": {
                        "path_to_attr_on_instance": ["id"],
                    },
                    "availability_zone": {
                        "path_to_attr_on_instance": ["availability_zone"],
                    },
                    "encrypted_flag": {
                        "path_to_attr_on_instance": ["encrypted"],
                    },
                    "bootable_flag": {
                        "path_to_attr_on_instance": ["bootable"],
                    },
                    "status": {
                        "path_to_attr_on_instance": ["status"],
                    },
                    "volume_type": {
                        "path_to_attr_on_instance": ["volume_type"],
                    },
                    "size": {
                        "path_to_attr_on_instance": ["size"],
                    },
                    "host": {
                        "path_to_attr_on_instance": ["os-vol-host-attr:host"],
                    },
                    "snapshot_id": {
                        "path_to_attr_on_instance": ["snapshot_id"],
                    },
                    "attachments": {
                        "path_to_attr_on_instance": ["attachments"],
                        "nested_attrs_to_collect": ["device", "server_id",
                                                    "id"],
                    },
                    "tenant_id": {
                        "path_to_attr_on_instance":
                        ["os-vol-tenant-attr:tenant_id"],
                    },
                },
                "resource_manager_name": "volumes",
                "additional_display_options": {
                    "search_opts": {"all_tenants": 1},
                },
            },
        }
    },
}
