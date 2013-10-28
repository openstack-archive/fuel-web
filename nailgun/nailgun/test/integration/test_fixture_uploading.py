# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

import cStringIO

from nailgun.api.models import Node
from nailgun.api.models import Release
from nailgun.fixtures.fixman import upload_fixture
from nailgun.test.base import BaseIntegrationTest


class TestFixture(BaseIntegrationTest):

    fixtures = ['admin_network', 'sample_environment']

    def test_upload_working(self):
        check = self.db.query(Node).all()
        self.assertEqual(len(list(check)), 8)

    def test_custom_fixture(self):
        data = '''[{
            "pk": 2,
            "model": "nailgun.release",
            "fields": {
                "name": "CustomFixtureRelease",
                "version": "0.0.1",
                "description": "Sample release for testing",
                "operating_system": "CentOS",
                "networks_metadata": {
                    "nova_network": {
                        "networks": [
                            {
                                "name": "floating",
                                "cidr": "172.16.0.0/24",
                                "netmask": "255.255.255.0",
                                "gateway": "172.16.0.1",
                                "ip_range": ["172.16.0.128", "172.16.0.254"],
                                "vlan_start": 100,
                                "network_size": 256,
                                "assign_vip": false
                            },
                            {
                                "name": "public",
                                "cidr": "172.16.0.0/24",
                                "netmask": "255.255.255.0",
                                "gateway": "172.16.0.1",
                                "ip_range": ["172.16.0.2", "172.16.0.127"],
                                "vlan_start": 100,
                                "assign_vip": true
                            },
                            {
                                "name": "management",
                                "cidr": "192.168.0.0/24",
                                "netmask": "255.255.255.0",
                                "gateway": "192.168.0.1",
                                "ip_range": ["192.168.0.1", "192.168.0.254"],
                                "vlan_start": 101,
                                "assign_vip": true
                            },
                            {
                                "name": "storage",
                                "cidr": "192.168.1.0/24",
                                "netmask": "255.255.255.0",
                                "gateway": "192.168.1.1",
                                "ip_range": ["192.168.1.1", "192.168.1.254"],
                                "vlan_start": 102,
                                "assign_vip": false
                            },
                            {
                                "name": "fixed",
                                "cidr": "10.0.0.0/16",
                                "netmask": "255.255.0.0",
                                "gateway": "10.0.0.1",
                                "ip_range": ["10.0.0.2", "10.0.255.254"],
                                "vlan_start": 103,
                                "assign_vip": false
                            }
                        ]
                    }
                }
            }
        }]'''

        upload_fixture(cStringIO.StringIO(data))
        check = self.db.query(Release).filter(
            Release.name == u"CustomFixtureRelease"
        )
        self.assertEqual(len(list(check)), 1)
