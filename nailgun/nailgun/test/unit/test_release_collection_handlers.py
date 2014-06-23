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

from nailgun.db.sqlalchemy.models import Release
from nailgun.openstack.common import jsonutils
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestHandlers(BaseIntegrationTest):
    def test_release_list_empty(self):
        resp = self.app.get(
            reverse('ReleaseCollectionHandler'),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        response = jsonutils.loads(resp.body)
        self.assertEqual([], response)

    def test_release_creation(self):
        resp = self.app.post(
            reverse('ReleaseCollectionHandler'),
            params=jsonutils.dumps({
                'name': 'Another test release',
                'version': '1.0',
                'operating_system': 'CentOS'
            }),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 201)

    def test_release_create(self):
        release_name = "OpenStack"
        release_version = "1.0.0"
        release_description = "This is test release"
        resp = self.app.post(
            reverse('ReleaseCollectionHandler'),
            jsonutils.dumps({
                'name': release_name,
                'version': release_version,
                'description': release_description,
                'operating_system': 'CentOS',
                'networks_metadata': {
                    "nova_network": {
                        "networks": [
                            {
                                "name": "storage",
                                "cidr": "192.168.1.0/24",
                                "gateway": "192.168.1.1",
                                "ip_range": [
                                    "192.168.1.1",
                                    "192.168.1.254"
                                ],
                                "vlan_start": 102,
                                "assign_vip": False
                            },
                            {
                                "name": "management",
                                "cidr": "10.0.0.0/16",
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
        self.assertEqual(resp.status_code, 201)

        resp = self.app.post(
            reverse('ReleaseCollectionHandler'),
            jsonutils.dumps({
                'name': release_name,
                'version': release_version,
                'description': release_description,
                'operating_system': 'CentOS',
                'networks_metadata': {
                    "nova_network": {
                        "networks": [
                            {
                                "name": "management",
                                "cidr": "10.0.0.0/16",
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
        self.assertEqual(resp.status_code, 409)

        release_from_db = self.db.query(Release).filter_by(
            name=release_name,
            version=release_version,
            description=release_description
        ).all()
        self.assertEqual(len(release_from_db), 1)

    def test_release_create_already_exist(self):
        release_name = "OpenStack"
        release_version = "1.0.0"
        release_description = "This is test release"
        resp = self.app.post(
            reverse('ReleaseCollectionHandler'),
            jsonutils.dumps({
                'name': release_name,
                'version': release_version,
                'description': release_description,
                'operating_system': 'CentOS',
                'networks_metadata': {
                    "nova_network": {
                        "networks": [
                            {
                                "name": "storage",
                                "cidr": "192.168.1.0/24",
                                "gateway": "192.168.1.1",
                                "ip_range": [
                                    "192.168.1.1",
                                    "192.168.1.254"
                                ],
                                "vlan_start": 102,
                                "assign_vip": False
                            },
                            {
                                "name": "management",
                                "cidr": "10.0.0.0/16",
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
        self.assertEqual(resp.status_code, 201)

        resp = self.app.post(
            reverse('ReleaseCollectionHandler'),
            jsonutils.dumps({
                'name': release_name,
                'version': release_version,
                'description': release_description,
                'operating_system': 'CentOS',
                'networks_metadata': {
                    "nova_network": {
                        "networks": [
                            {
                                "name": "management",
                                "cidr": "10.0.0.0/16",
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
        self.assertEqual(resp.status_code, 409)

    def test_release_w_orch_data_create(self):
        release_name = "OpenStack"
        release_version = "1.0.0"
        release_description = "This is a release w orchestrator data"
        orch_data = {
            "repo_metadata": {
                "nailgun":
                "http://10.20.0.2:8080/centos-5.0/centos/fuelweb/x86_64/"
            },
            "puppet_modules_source":
            "rsync://10.20.0.2/puppet/release/5.0/modules",
            "puppet_manifests_source":
            "rsync://10.20.0.2/puppet/release/5.0/manifests"
        }
        resp = self.app.post(
            reverse('ReleaseCollectionHandler'),
            jsonutils.dumps({
                'name': release_name,
                'version': release_version,
                'description': release_description,
                'operating_system': 'CentOS',
                "orchestrator_data": orch_data,
                'networks_metadata': {
                    "nova_network": {
                        "networks": [
                            {
                                "name": "storage",
                                "cidr": "192.168.1.0/24",
                                "gateway": "192.168.1.1",
                                "ip_range": [
                                    "192.168.1.1",
                                    "192.168.1.254"
                                ],
                                "vlan_start": 102,
                                "assign_vip": False
                            },
                            {
                                "name": "management",
                                "cidr": "10.0.0.0/16",
                                "gateway": "10.0.0.1",
                                "ip_range": [
                                    "10.0.0.2",
                                    "10.0.255.254"
                                ],
                                "vlan_start": 103,
                                "assign_vip": False
                            }]
                    }
                }
            }),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 201)

        resp = self.app.get(
            reverse("ReleaseCollectionHandler"),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        response = jsonutils.loads(resp.body)
        self.assertEqual(1, len(response))
        self.assertEqual(orch_data, response[0]["orchestrator_data"])
