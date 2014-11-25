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


# "*" means any key name
# "" means any value
task_output_white_list = {
    consts.TASK_NAMES.provision: {
        "method": "",
        "api_version": "",
        "args": {
            "task_uuid": "",
            "provisioning_info": {
                "engine": {
                    "provision_method": ""
                },
                "nodes": {
                    "uid": "",
                    "interfaces": {
                        "*": {
                            "static": "",
                            "netmask": ""
                        }
                    },
                    "interfaces_extra": {
                        "*": {
                            "onboot": "",
                            "peerdns": ""
                        }
                    },
                    "ks_meta": {
                        "mco_enable": "",
                        "mlnx_iser_enabled": "",
                        "puppet_enable": "",
                        "fuel_version": "",
                        "install_log_2_syslog": "",
                        "timezone": "",
                        "puppet_auto_setup": "",
                        "mco_auto_setup": "",
                        "pm_data": {
                            "kernel_params": "",
                            "ks_spaces": {
                                "id": "",
                                "name": "",
                                "extra": "",
                                "type": "",
                                "size": "",
                                "volumes": {
                                    "type": "",
                                    "size": "",
                                    "vg": "",
                                }
                            }
                        },
                        "mlnx_plugin_mode": "",
                        "mco_connector": "",
                        "mlnx_vf_num": ""
                    },
                    "netboot_enabled": ""
                }
            }
        }
    },
    consts.TASK_NAMES.deployment: {
        "method": "",
        "api_version": "",
        "args": {
            "task_uuid": "",
            "deployment_info": {
                "uid": "",
                "use_cow_images": "",
                "syslog": {
                    "syslog_transport": ""
                },
                "libvirt_type": "",
                "sahara": {
                    "enabled": ""
                },
                "nsx_plugin": {
                    "replication_mode": "",
                    "connector_type": "",
                    "metadata": {
                        "enabled": ""
                    }
                },
                "quantum": "",
                "glance": {
                    "image_cache_max_size": ""
                },
                "cobbler": {
                    "profile": ""
                },
                "quantum_settings": {
                    "L3": {
                        "use_namespaces": ""
                    },
                    "L2": {
                        "phys_nets": "",
                        "segmentation_type": "",
                        "tunnel_id_ranges": ""
                    },
                    "predefined_networks": {
                        "*": {
                            "shared": "",
                            "L2": {
                                "network_type": "",
                                "router_ext": "",
                                "physnet": "",
                                "segment_id": ""
                            },
                            "L3": {
                                "enable_dhcp": ""
                            },
                            "tenant": ""
                        }
                    }
                },
                "openstack_version": "",
                "nova_quota": "",
                "provision": {
                    "image_data": {
                        "*": {
                            "container": "",
                            "uri": "",
                            "format": ""
                        }
                    },
                    "method": "",
                },
                "resume_guests_state_on_host_boot": "",
                "storage": {
                    "iser": "",
                    "volumes_ceph": "",
                    "objects_ceph": "",
                    "volumes_lvm": "",
                    "osd_pool_size": "",
                    "images_vcenter": "",
                    "ephemeral_ceph": "",
                    "vc_image_dir": "",
                    "volumes_vmdk": "",
                    "pg_num": "",
                    "images_ceph": ""
                },
                "compute_scheduler_driver": "",
                "nova": {
                    "state_path": ""
                },
                "priority": "",
                "murano": {
                    "enabled": ""
                },
                "role": "",
                "online": "",
                "vcenter": {
                    "use_vcenter": ""
                },
                "auto_assign_floating_ip": "",
                "ceilometer": {
                    "enabled": ""
                },
                "corosync": {
                    "verified": ""
                },
                "status": "",
                "deployment_mode": "",
                "fail_if_error": "",
                "puppet_manifests_source": "",
                "network_scheme": {
                    "transformations": {
                        "*": "",
                    },
                    "roles": {
                        "*": ""
                    },
                    "interfaces": {
                        "*": {
                            "L2": {
                                "vlan_splinters": ""
                            }
                        }
                    },
                    "version": "",
                    "provider": "",
                    "endpoints": {
                        "*": {
                            "other_nets": {},
                            "default_gateway": ""
                        }
                    }
                },
                "heat": {
                    "enabled": ""
                },
                "test_vm_image": {
                    "os_name": "",
                    "container_format": "",
                    "min_ram": "",
                    "disk_format": "",
                    "glance_properties": "",
                    "img_name": "",
                    "public": ""
                },
                "fuel_version": "",
                "public_network_assignment": {
                    "assign_to_all_nodes": ""
                },
                "use_cinder": "",
                "nodes": {
                    "uid": "",
                    "role": ""
                },
                "repo_metadata": {
                    "nailgun": ""
                },
                "kernel_params": {
                    "kernel": ""
                },
                "neutron_mellanox": {
                    "vf_num": "",
                    "plugin": "",
                    "metadata": {
                        "enabled": ""
                    }
                },
                "puppet_modules_source": "",
                "debug": "",
                "deployment_id": "",
                "openstack_version_prev": ""
            },
            "pre_deployment": {
                "*": {}
            },
            "post_deployment": {
                "*": {}
            }
        }
    }
}
