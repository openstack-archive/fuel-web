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


from nailgun.db.sqlalchemy.models import fencing


fencing_metadata = {
    "primitives_ui_parameters": {
        "common": {
            "parameters": ["ipaddr", "login", "passwd"]
        },
        "virsh": {
            "type": "power",
            "per_node_relation": 1,
            "parameters": []
        },
        "ipmilan": {
            "type": "remote",
            "per_node_relation": 1,
            "parameters": []
        },
        "ilo": {
            "type": "remote",
            "per_node_relation": 1,
            "parameters": []
        },
        "apc": {
            "type": "power",
            "per_node_relation": 2,
            "parameters": ["port", "secure"]
        },
        "apc_snmp": {
            "type": "power",
            "per_node_relation": 2,
            "parameters": ["port", "snmp_version", "community",
                           "snmp_sec_level", "snmp_auth_prot",
                           "snmp_priv_prot", "snmp_priv_passwd"]
        },
        "drac5": {
            "type": "remote",
            "per_node_relation": 1,
            "parameters": ["cmd_prompt", "drac_version", "module_name",
                           "secure"]
        }
    },
    "primitives_all_parameters": {
        "common": {
            "operations": {
                "monitor": {
                    "interval": "3600s",
                    "timeout": "120s"
                },
                "start": {
                    "interval": "0",
                    "timeout": "120s",
                    "on-fail": "restart"
                },
                "stop": {
                    "interval": "0",
                    "timeout": "1800s",
                    "on-fail": "restart"
                }
            },
            "meta": {
                "migration-threshold": "5",
                "failure-timeout": "180"
            },
            "parameters": {
                "ipaddr": "",  # set via API
                "login": "",  # set via API
                "passwd": "",  # set via API
                "delay": "10",  # "30" for primary_controller else "10"
                "action": "",  # reboot/off (remote group) off/on (power group)
                "pcmk_reboot_action": "",  # reboot/off or off/on
                "pcmk_off_action": ""  # reboot/off or off/on
            }
        },
        "virsh": {
            "agent_type": "fence_virsh",
            "parameters": {
                "power_timeout": "30",
                "shell_timeout": "10",
                "login_timeout": "10",
                "power_wait": "15",
                "pcmk_host_argument": "uuid",
                "pcmk_host_map": ""  # node_uname:facter_uuid
            }
        },
        "ipmilan": {
            "agent_type": "fence_ipmilan",
            "parameters": {
                "privlvl": "operator",
                "auth": "password",
                "power_wait": "15",
                "pcmk_host_list": ""  # node_uname
            }
        },
        "ilo": {
            "agent_type": "fence_ipmilan",
            "parameters": {
                "privlvl": "operator",
                "auth": "password",
                "lanplus": "true",
                "power_wait": "15",
                "pcmk_host_list": ""  # node_uname
            }
        },
        "apc": {
            "agent_type": "fence_apc",
            "parameters": {
                "port": "",  # set via API
                "power_timeout": "30",
                "shell_timeout": "20",
                "login_timeout": "20",
                "power_wait": "15",
                "secure": "true",
                "pcmk_host_list": ""  # node_uname
            }
        },
        "apc_snmp": {
            "agent_type": "fence_apc_snmp",
            "parameters": {
                "port": "",  # set via API
                "snmp_version": "",  # set via API
                "community": "",  # set via API
                "snmp_sec_level": "",  # set via API
                "snmp_auth_prot": "",  # set via API
                "snmp_priv_prot": "",  # set via API
                "snmp_priv_passwd": "",  # set via API
                "power_timeout": "30",
                "shell_timeout": "10",
                "login_timeout": "10",
                "power_wait": "15",
                "pcmk_host_list": ""  # node_uname
            }
        },
        "drac5": {
            "agent_type": "fence_drac5",
            "parameters": {
                "module_name": "",  # set via API
                "drac_version": "2",  # set via API
                "secure": "true",  # set via API
                "cmd_prompt": "\\$",  # set via API
                "power_timeout": "30",
                "shell_timeout": "10",
                "login_timeout": "10",
                "power_wait": "15",
                "pcmk_host_list": ""  # node_uname
            }
        }
    },
    "request_data_format": {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "title": "FencingConfiguration",
        "description": "Fencing API request data format",
        "type": "object",
        "required": [
            "policy",
            "primitive_configuration"
        ],
        "properties": {
            "policy": {
                "type": "string",
                "enum": list(fencing.FENCING_POLICIES)
            },
            "primitive_configuration": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name", "node_primitive_configuration"],
                    "properties": {
                        "name": {
                            "type": "string",
                            "enum": list(fencing.FENCING_PRIM_NAMES)
                        },
                        "node_primitive_configuration": {
                            "description": "",
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["node_id", "index", "parameters"],
                                "properties": {
                                    "node_id": {"type": "integer"},
                                    "index": {"type": "integer"},
                                    "parameters": {
                                        "type": "object",
                                        "required": ["ipaddr", "login",
                                                     "passwd"],
                                        "properties": {
                                            "ipaddr": {"type": "string"},
                                            "login": {"type": "string"},
                                            "passwd": {"type": "string"},
                                            "port": {"type": "string"},
                                            "secure": {"type": "string"},
                                            "snmp_version": {"type": "string"},
                                            "community": {"type": "string"},
                                            "snmp_sec_level": {
                                                "type": "string"},
                                            "snmp_auth_prot": {
                                                "type": "string"},
                                            "snmp_priv_prot": {
                                                "type": "string"},
                                            "snmp_priv_passwd": {
                                                "type": "string"},
                                            "cmd_prompt": {"type": "string"},
                                            "drac_version": {"type": "string"},
                                            "module_name": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
