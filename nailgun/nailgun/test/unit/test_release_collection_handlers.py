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

import json

from nailgun.api.models import Release
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestHandlers(BaseIntegrationTest):
    def test_release_list_empty(self):
        resp = self.app.get(
            reverse('ReleaseCollectionHandler'),
            headers=self.default_headers
        )
        self.assertEquals(200, resp.status)
        response = json.loads(resp.body)
        self.assertEquals([], response)

    def test_release_creation(self):
        resp = self.app.post(
            reverse('ReleaseCollectionHandler'),
            params=json.dumps({
                'name': 'Another test release',
                'version': '1.0',
                'operating_system': 'CentOS'
            }),
            headers=self.default_headers
        )
        self.assertEquals(resp.status, 201)

    def test_release_create(self):
        release_name = "OpenStack"
        release_version = "1.0.0"
        release_description = "This is test release"
        resp = self.app.post(
            reverse('ReleaseCollectionHandler'),
            json.dumps({
                'name': release_name,
                'version': release_version,
                'description': release_description,
                'operating_system': 'CentOS',
                'networks_metadata': {
                    "nova_network": {
                        "networks": [
                            {
                                "name": "floating",
                                "cidr": "172.16.0.0/24",
                                "netmask": "255.255.255.0",
                                "gateway": "172.16.0.1",
                                "ip_range": [
                                    "172.16.0.128",
                                    "172.16.0.254"
                                ],
                                "vlan_start": 100,
                                "network_size": 256,
                                "assign_vip": False
                            },
                            {
                                "name": "storage",
                                "cidr": "192.168.1.0/24",
                                "netmask": "255.255.255.0",
                                "gateway": "192.168.1.1",
                                "ip_range": [
                                    "192.168.1.1",
                                    "192.168.1.254"
                                ],
                                "vlan_start": 102,
                                "assign_vip": False
                            },
                            {
                                "name": "fixed",
                                "cidr": "10.0.0.0/16",
                                "netmask": "255.255.0.0",
                                "gateway": "10.0.0.1",
                                "ip_range": [
                                    "10.0.0.2",
                                    "10.0.255.254"
                                ],
                                "vlan_start": 103,
                                "assign_vip": False
                            }
                        ]
                    }
                }
            }),
            headers=self.default_headers
        )
        self.assertEquals(resp.status, 201)

        resp = self.app.post(
            reverse('ReleaseCollectionHandler'),
            json.dumps({
                'name': release_name,
                'version': release_version,
                'description': release_description,
                'operating_system': 'CentOS',
                'networks_metadata': {
                    "nova_network": {
                        "networks": [
                            {
                                "name": "fixed",
                                "cidr": "10.0.0.0/16",
                                "netmask": "255.255.0.0",
                                "gateway": "10.0.0.1",
                                "ip_range": [
                                    "10.0.0.2",
                                    "10.0.255.254"
                                ],
                                "vlan_start": 103,
                                "assign_vip": False
                            }
                        ]
                    }
                }
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEquals(resp.status, 409)

        release_from_db = self.db.query(Release).filter_by(
            name=release_name,
            version=release_version,
            description=release_description
        ).all()
        self.assertEquals(len(release_from_db), 1)

    def test_release_create_already_exist(self):
        release_name = "OpenStack"
        release_version = "1.0.0"
        release_description = "This is test release"
        resp = self.app.post(
            reverse('ReleaseCollectionHandler'),
            json.dumps({
                'name': release_name,
                'version': release_version,
                'description': release_description,
                'operating_system': 'CentOS',
                'networks_metadata': {
                    "nova_network": {
                        "networks": [
                            {
                                "name": "floating",
                                "cidr": "172.16.0.0/24",
                                "netmask": "255.255.255.0",
                                "gateway": "172.16.0.1",
                                "ip_range": [
                                    "172.16.0.128",
                                    "172.16.0.254"
                                ],
                                "vlan_start": 100,
                                "network_size": 256,
                                "assign_vip": False
                            },
                            {
                                "name": "storage",
                                "cidr": "192.168.1.0/24",
                                "netmask": "255.255.255.0",
                                "gateway": "192.168.1.1",
                                "ip_range": [
                                    "192.168.1.1",
                                    "192.168.1.254"
                                ],
                                "vlan_start": 102,
                                "assign_vip": False
                            },
                            {
                                "name": "fixed",
                                "cidr": "10.0.0.0/16",
                                "netmask": "255.255.0.0",
                                "gateway": "10.0.0.1",
                                "ip_range": [
                                    "10.0.0.2",
                                    "10.0.255.254"
                                ],
                                "vlan_start": 103,
                                "assign_vip": False
                            }
                        ]
                    }
                }
            }),
            headers=self.default_headers
        )
        self.assertEquals(resp.status, 201)

        resp = self.app.post(
            reverse('ReleaseCollectionHandler'),
            json.dumps({
                'name': release_name,
                'version': release_version,
                'description': release_description,
                'operating_system': 'CentOS',
                'networks_metadata': {
                    "nova_network": {
                        "networks": [
                            {
                                "name": "fixed",
                                "cidr": "10.0.0.0/16",
                                "netmask": "255.255.0.0",
                                "gateway": "10.0.0.1",
                                "ip_range": [
                                    "10.0.0.2",
                                    "10.0.255.254"
                                ],
                                "vlan_start": 103,
                                "assign_vip": False
                            }
                        ]
                    }
                }
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEquals(resp.status, 409)
