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


def get_default_release_settings():
    """Get default release settings.

    :return: release configuration
    :rtype: dict
    """
    return {
        "attributes_metadata": {"editable": {}},
        "networks_metadata": {
            "neutron": {
                "config": {
                    "vlan_range": [
                        1000,
                        1030
                    ],
                    "gre_id_range": [
                        2,
                        65535
                    ],
                    "base_mac": "fa:16:3e:00:00:00",
                    "internal_name": "admin_internal_net",
                    "internal_cidr": "192.168.111.0/24",
                    "internal_gateway": "192.168.111.1",
                    "floating_name": "admin_floating_net",
                    "floating_ranges": [
                        [
                            "172.16.0.130",
                            "172.16.0.254"
                        ]
                    ],
                    "baremetal_gateway": "192.168.3.51",
                    "baremetal_range": [
                        "192.168.3.52",
                        "192.168.3.254"
                    ],
                    "parameters": None,
                    "amqp": None,
                    "provider": "mysql",
                    "username": None,
                    "passwd": "",
                    "hosts": "hostname1:5672, hostname2:5672",
                    "database": None,
                    "port": "3306",
                    "keystone": None,
                    "admin_user": None,
                    "admin_password": "",
                    "metadata": None,
                    "metadata_proxy_shared_secret": ""
                },
                "networks": [
                    {
                        "name": "public",
                        "cidr": "172.16.0.0/24",
                        "ip_range": [
                            "172.16.0.2",
                            "172.16.0.126"
                        ],
                        "vlan_start": None,
                        "use_gateway": True,
                        "notation": "ip_ranges",
                        "render_type": None,
                        "render_addr_mask": "public",
                        "map_priority": 1,
                        "configurable": True,
                        "floating_range_var": "floating_ranges",
                        "vips": [
                            "haproxy",
                            "vrouter"
                        ]
                    },
                    {
                        "name": "management",
                        "cidr": "192.168.0.0/24",
                        "vlan_start": 101,
                        "use_gateway": False,
                        "notation": "cidr",
                        "render_type": "cidr",
                        "render_addr_mask": "internal",
                        "map_priority": 2,
                        "configurable": True,
                        "vips": [
                            "haproxy",
                            "vrouter"
                        ]
                    },
                    {
                        "name": "storage",
                        "cidr": "192.168.1.0/24",
                        "vlan_start": 102,
                        "use_gateway": False,
                        "notation": "cidr",
                        "render_type": "cidr",
                        "render_addr_mask": "storage",
                        "map_priority": 2,
                        "configurable": True
                    },
                    {
                        "name": "private",
                        "seg_type": "vlan",
                        "vlan_start": None,
                        "use_gateway": False,
                        "notation": None,
                        "render_type": None,
                        "render_addr_mask": None,
                        "map_priority": 2,
                        "neutron_vlan_range": True,
                        "configurable": False
                    },
                    {
                        "name": "private",
                        "seg_type": "gre",
                        "cidr": "192.168.2.0/24",
                        "vlan_start": 103,
                        "use_gateway": False,
                        "notation": "cidr",
                        "render_type": "cidr",
                        "render_addr_mask": None,
                        "map_priority": 2,
                        "configurable": True
                    },
                    {
                        "name": "private",
                        "seg_type": "tun",
                        "cidr": "192.168.2.0/24",
                        "vlan_start": 103,
                        "use_gateway": False,
                        "notation": "cidr",
                        "render_type": "cidr",
                        "render_addr_mask": None,
                        "map_priority": 2,
                        "configurable": True
                    },
                    {
                        "name": "baremetal",
                        "cidr": "192.168.3.0/24",
                        "ip_range": [
                            "192.168.3.2",
                            "192.168.3.50"
                        ],
                        "vlan_start": 104,
                        "use_gateway": False,
                        "notation": "ip_ranges",
                        "render_type": None,
                        "map_priority": 2,
                        "configurable": True,
                        "restrictions": [
                            {
                                "condition": "settings:additional_components."
                                             "ironic.value == false"
                            }
                        ]
                    }
                ]
            }
        }
    }
