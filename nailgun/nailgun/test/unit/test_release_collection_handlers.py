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
from mock import patch
from nailgun.db.sqlalchemy.models import Release
from nailgun.openstack.common import jsonutils
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse
from uuid import uuid4


class TestHandlers(BaseIntegrationTest):
    def test_release_list_empty(self):
        resp = self.app.get(
            reverse('ReleaseCollectionHandler'),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual([], resp.json_body)

    def test_release_creation(self):
        resp = self.app.post(
            reverse('ReleaseCollectionHandler'),
            params=jsonutils.dumps({
                'name': 'Another test release',
                'version': '1.0',
                'operating_system': 'CentOS',
                'orchestrator_data':
                self.env.get_default_orchestrator_data(),
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
                },
                'orchestrator_data':
                self.env.get_default_orchestrator_data(),
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
                },
                'orchestrator_data':
                self.env.get_default_orchestrator_data()
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
                },
                'orchestrator_data':
                self.env.get_default_orchestrator_data()
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
                },
                'orchestrator_data':
                self.env.get_default_orchestrator_data(),
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
                "http://10.20.0.2:8080/centos-5.0/centos/x86_64/"
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
        self.assertEqual(1, len(resp.json_body))
        self.assertEqual(orch_data, resp.json_body[0]["orchestrator_data"])


class ReleaseCollectionSortBaseTest(BaseIntegrationTest):
    releases = []
    expected = []

    def setUp(self):
        super(ReleaseCollectionSortBaseTest, self).setUp()
        for r in self.releases:
            self.env.create_release(**{
                'version': r[0],
                'operating_system': r[1],
                'name': 'release_name_{0}'.format(uuid4())
            })

    def test_release_collection_order(self):
        resp = self.app.get(
            reverse('ReleaseCollectionHandler'),
            headers=self.default_headers
        ).json_body

        actual = [(r['version'], r['operating_system']) for r in resp]

        self.assertEqual(actual, self.expected)


@patch('nailgun.objects.release.settings.DEFAULT_REPO',
       dict.fromkeys(['centos', 'ubuntu', 'arch', 'debian', 'fedora'], ''))
class TestReleaseCollectionSortingAllCriteria(ReleaseCollectionSortBaseTest):
    releases = [
        ("2014.1-6.0", "Ubuntu"),
        ("2014.2-5.1.1", "Ubuntu"),
        ("2013.2.1-5.1", "CentOS"),
        ("2013.2.1-5.1", "Debian"),
        ("2014.3", "Ubuntu"),
        ("2013.2", "CentOS"),
        ("2013.2", "Ubuntu"),
        ("2014.3-7.0", "CentOS"),
        ("2014.1.3-5.1.1", "CentOS"),
        ("2013.2-5.0", "CentOS"),
        ("2014.3", "CentOS"),
        ("2014.2-6.0", "Ubuntu"),
        ("2013.2.1-5.1", "Fedora"),
        ("2014.2-6.1", "CentOS"),
        ("2014.2-6.0", "CentOS"),
        ("2014.2-5.1.1", "CentOS"),
        ("2013.2.1-5.1", "Ubuntu"),
        ("2013.2-4.0", "Ubuntu"),
        ("2014.3", "Arch"),
        ("2014.2.2-6.0", "CentOS"),
        ("2014.1-5.1.1", "Ubuntu")
    ]

    expected = [
        ("2014.3-7.0", "CentOS"),
        ("2014.2-6.1", "CentOS"),
        ("2014.2.2-6.0", "CentOS"),
        ("2014.2-6.0", "Ubuntu"),
        ("2014.2-6.0", "CentOS"),
        ("2014.1-6.0", "Ubuntu"),
        ("2014.2-5.1.1", "Ubuntu"),
        ("2014.2-5.1.1", "CentOS"),
        ("2014.1.3-5.1.1", "CentOS"),
        ("2014.1-5.1.1", "Ubuntu"),
        ("2013.2.1-5.1", "Ubuntu"),
        ("2013.2.1-5.1", "CentOS"),
        ("2013.2.1-5.1", "Debian"),
        ("2013.2.1-5.1", "Fedora"),
        ("2013.2-5.0", "CentOS"),
        ("2013.2-4.0", "Ubuntu"),
        ("2014.3", "Ubuntu"),
        ("2014.3", "CentOS"),
        ("2014.3", "Arch"),
        ("2013.2", "Ubuntu"),
        ("2013.2", "CentOS"),
    ]


class TestReleaseCollectionSortByFuelVersion(ReleaseCollectionSortBaseTest):
    releases = [
        ("-7.1", "CentOS"),
        ("-7.0", "CentOS"),
        ("-6.0", "CentOS"),
        ("-6", "CentOS"),
    ]

    expected = [
        ("-7.1", "CentOS"),
        ("-7.0", "CentOS"),
        ("-6.0", "CentOS"),
        ("-6", "CentOS"),
    ]


class TestReleaseCollectionSortByOpenstack(ReleaseCollectionSortBaseTest):
    releases = [
        ("2013.2", "Ubuntu"),
        ("2011.1-", "Ubuntu"),
        ("2014.3-", "Ubuntu"),
        ("2012.3-", "Ubuntu"),
        ("2013.4-", "Ubuntu"),
    ]

    expected = [
        ("2014.3-", "Ubuntu"),
        ("2013.4-", "Ubuntu"),
        ("2013.2", "Ubuntu"),
        ("2012.3-", "Ubuntu"),
        ("2011.1-", "Ubuntu"),
    ]


@patch('nailgun.objects.release.settings.DEFAULT_REPO',
       dict.fromkeys(['centos', 'ubuntu', 'arch', 'debian', 'fedora'], ''))
class TestReleaseCollectionSortByOS(ReleaseCollectionSortBaseTest):
    releases = [
        ("X", "Debian"),
        ("X", "Fedora"),
        ("X", "Arch"),
        ("X", "CentOS"),
        ("X", "Ubuntu"),
    ]

    expected = [
        ("X", "Ubuntu"),
        ("X", "CentOS"),
        ("X", "Arch"),
        ("X", "Debian"),
        ("X", "Fedora"),
    ]
