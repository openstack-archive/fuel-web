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
_task_output_white_list_template = {
    "provision_template": {
        "method": "",
        "respond_to": "",
        "api_version": "",
        "args": {
            "task_uuid": "",
            "provisioning_info": {
                "engine": {
                    "provision_method": ""
                },
                "nodes": {
                    "uid": "",
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
    "deployment_template": {
        "method": "",
        "respond_to": "",
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
                            }
                        }
                    }
                },
                "openstack_version": "",
                "nova_quota": "",
                "provision": {
                    "image_data": {
                        "*": {
                            "container": "",
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
                "network_scheme": {
                    "roles": {
                        "*": ""
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
    },
    "delete_template": {
        "method": "",
        "respond_to": "",
        "api_version": "",
        "args": {
            "task_uuid": "",
            "nodes": {
                "id": "",
                "uid": "",
                "roles": ""
            }
        }
    },
    "dump_template": {
        "method": "",
        "respond_to": "",
        "api_version": "",
        "args": {
            "task_uuid": "",
            "settings": {
                'timestamp': "",
                'lastdump': "",
                'target': "",
                'dump': {
                    '*': {
                        'objects': {
                            'type': "",
                            'command': "",
                            'path': "",
                        },
                        'hosts': {}
                    }
                }
            }
        }
    },
    "networks_verify_template": {
        "method": "",
        "respond_to": "",
        "api_version": "",
        "args": {
            "task_uuid": "",
            "nodes": {
                "uid": ""
            }
        },
        "subtasks": {
            "method": "",
            "respond_to": "",
            "api_version": "",
            "args": {
                "task_uuid": ""
            }
        }
    }
}


task_output_white_list = {
    consts.TASK_NAMES.provision:
    _task_output_white_list_template["provision_template"],
    consts.TASK_NAMES.deployment:
    _task_output_white_list_template["deployment_template"],
    consts.TASK_NAMES.update:
    _task_output_white_list_template["deployment_template"],

    consts.TASK_NAMES.node_deletion:
    _task_output_white_list_template["delete_template"],
    consts.TASK_NAMES.cluster_deletion:
    _task_output_white_list_template["delete_template"],
    consts.TASK_NAMES.reset_environment:
    _task_output_white_list_template["delete_template"],
    consts.TASK_NAMES.stop_deployment:
    _task_output_white_list_template["delete_template"],

    consts.TASK_NAMES.verify_networks:
    _task_output_white_list_template["networks_verify_template"],
    consts.TASK_NAMES.check_dhcp:
    _task_output_white_list_template["networks_verify_template"],
    consts.TASK_NAMES.multicast_verification:
    _task_output_white_list_template["networks_verify_template"],

    consts.TASK_NAMES.dump:
    _task_output_white_list_template["dump_template"],
}
