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
import json
import os
import yaml

from nailgun.db.sqlalchemy.fixman import upload_fixture
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import Release
from nailgun.test.base import BaseIntegrationTest


class TestFixture(BaseIntegrationTest):

    fixtures = ['admin_network', 'sample_environment']

    # def test_upload_working(self):
    #     check = self.db.query(Node).all()
    #     self.assertEqual(len(list(check)), 8)

    # def test_custom_fixture(self):
    #     data = '''[{
    #         "pk": 2,
    #         "model": "nailgun.release",
    #         "fields": {
    #             "name": "CustomFixtureRelease",
    #             "version": "0.0.1",
    #             "description": "Sample release for testing",
    #             "operating_system": "CentOS",
    #             "networks_metadata": {
    #                 "nova_network": {
    #                     "networks": [
    #                         {
    #                             "name": "floating",
    #                             "cidr": "172.16.0.0/24",
    #                             "netmask": "255.255.255.0",
    #                             "gateway": "172.16.0.1",
    #                             "ip_range": ["172.16.0.128", "172.16.0.254"],
    #                             "vlan_start": 100,
    #                             "network_size": 256,
    #                             "assign_vip": false
    #                         },
    #                         {
    #                             "name": "public",
    #                             "cidr": "172.16.0.0/24",
    #                             "netmask": "255.255.255.0",
    #                             "gateway": "172.16.0.1",
    #                             "ip_range": ["172.16.0.2", "172.16.0.127"],
    #                             "vlan_start": 100,
    #                             "assign_vip": true
    #                         },
    #                         {
    #                             "name": "management",
    #                             "cidr": "192.168.0.0/24",
    #                             "netmask": "255.255.255.0",
    #                             "gateway": "192.168.0.1",
    #                             "ip_range": ["192.168.0.1", "192.168.0.254"],
    #                             "vlan_start": 101,
    #                             "assign_vip": true
    #                         },
    #                         {
    #                             "name": "storage",
    #                             "cidr": "192.168.1.0/24",
    #                             "netmask": "255.255.255.0",
    #                             "gateway": "192.168.1.1",
    #                             "ip_range": ["192.168.1.1", "192.168.1.254"],
    #                             "vlan_start": 102,
    #                             "assign_vip": false
    #                         },
    #                         {
    #                             "name": "fixed",
    #                             "cidr": "10.0.0.0/16",
    #                             "netmask": "255.255.0.0",
    #                             "gateway": "10.0.0.1",
    #                             "ip_range": ["10.0.0.2", "10.0.255.254"],
    #                             "vlan_start": 103,
    #                             "assign_vip": false
    #                         }
    #                     ]
    #                 }
    #             }
    #         }
    #     }]'''

    #     upload_fixture(cStringIO.StringIO(data), loader=json)
    #     check = self.db.query(Release).filter(
    #         Release.name == u"CustomFixtureRelease"
    #     )
    #     self.assertEqual(len(list(check)), 1)

    # def test_fixture_roles_order(self):
    #     data = '''[{
    #         "pk": 1,
    #         "model": "nailgun.release",
    #         "fields": {
    #             "name": "CustomFixtureRelease1",
    #             "version": "0.0.1",
    #             "description": "Sample release for testing",
    #             "operating_system": "CentOS",
    #             "roles": ["controller", "compute", "cinder", "ceph-osd"]
    #         }
    #     }]'''
    #     upload_fixture(cStringIO.StringIO(data), loader=json)
    #     rel = self.db.query(Release).filter(
    #         Release.name == u"CustomFixtureRelease1"
    #     ).all()
    #     self.assertEqual(len(rel), 1)
    #     self.assertEqual(list(rel[0].roles),
    #                      ["controller", "compute", "cinder", "ceph-osd"])

    #     data = '''[{
    #         "pk": 2,
    #         "model": "nailgun.release",
    #         "fields": {
    #             "name": "CustomFixtureRelease2",
    #             "version": "0.0.1",
    #             "description": "Sample release for testing",
    #             "operating_system": "CentOS",
    #             "roles": ["compute", "ceph-osd", "controller", "cinder"]
    #         }
    #     }]'''
    #     upload_fixture(cStringIO.StringIO(data), loader=json)
    #     rel = self.db.query(Release).filter(
    #         Release.name == u"CustomFixtureRelease2"
    #     ).all()
    #     self.assertEqual(len(rel), 1)
    #     self.assertEqual(list(rel[0].roles),
    #                      ["compute", "ceph-osd", "controller", "cinder"])

    #     data = '''[{
    #         "pk": 3,
    #         "model": "nailgun.release",
    #         "fields": {
    #             "name": "CustomFixtureRelease3",
    #             "version": "0.0.1",
    #             "description": "Sample release for testing",
    #             "operating_system": "CentOS",
    #             "roles": ["compute", "cinder", "controller", "cinder"]
    #         }
    #     }]'''
    #     upload_fixture(cStringIO.StringIO(data), loader=json)
    #     rel = self.db.query(Release).filter(
    #         Release.name == u"CustomFixtureRelease3"
    #     ).all()
    #     self.assertEqual(len(rel), 1)
    #     self.assertEqual(list(rel[0].roles),
    #                      ["compute", "cinder", "controller"])
    #     # check previously added release roles
    #     prev_rel = self.db.query(Release).filter(
    #         Release.name == u"CustomFixtureRelease2"
    #     ).all()
    #     self.assertEqual(len(prev_rel), 1)
    #     self.assertEqual(list(prev_rel[0].roles),
    #                      ["compute", "ceph-osd", "controller", "cinder"])

    def test_custom_yaml_fixture(self):
        data = '''---
                    - &base_release
                      model: "nailgun.release"
                      fields:
                        state: "available"
                        networks_metadata:
                          nova_network:
                            networks:
                              - name: "floating"
                                cidr: "172.16.0.0/24"
                                ip_range: ["172.16.0.128", "172.16.0.254"]
                                vlan_start: null
                                use_gateway: false
                                notation: "ip_ranges"
                                render_type: "ip_ranges"
                                render_addr_mask: null
                                use_same_vlan_nic: 1
                                map_priority: 1
                                assign_vip: false
                              - name: "public"
                                cidr: "172.16.0.0/24"
                                netmask: "255.255.255.0"
                                gateway: "172.16.0.1"
                                ip_range: ["172.16.0.2", "172.16.0.127"]
                                vlan_start: null
                                use_gateway: true
                                notation: "ip_ranges"
                                calculate_cidr: true
                                render_type: null
                                render_addr_mask: "public"
                                use_same_vlan_nic: 1
                                map_priority: 1
                                assign_vip: true
                              - name: "management"
                                cidr: "192.168.0.0/24"
                                vlan_start: 101
                                use_gateway: false
                                notation: "cidr"
                                render_type: "cidr"
                                render_addr_mask: "internal"
                                map_priority: 2
                                assign_vip: true
                              - name: "storage"
                                cidr: "192.168.1.0/24"
                                vlan_start: 102
                                use_gateway: false
                                notation: "cidr"
                                render_type: "cidr"
                                render_addr_mask: "storage"
                                map_priority: 2
                                assign_vip: false
                              - name: "fixed"
                                cidr: "10.0.0.0/16"
                                network_size: 256
                                vlan_start: 103
                                use_gateway: true
                                notation: "cidr"
                                render_type: "cidr"
                                render_addr_mask: null
                                map_priority: 2
                                assign_vip: false
                    - &full_release
                      extend: *base_release
                      fields:
                        roles:
                          - controller
                          - compute
                          - cinder
                          - ceph-osd
                        roles_metadata:
                          ceph-osd:
                            name: "Storage - Ceph OSD"
                            description: "Ceph storage."
                        networks_metadata:
                          neutron:
                            networks:
                              - name: "public"
                                cidr: "172.16.0.0/24"
                                ip_range: ["172.16.0.2", "172.16.0.126"]
                                vlan_start: null
                                use_gateway: true
                                notation: "ip_ranges"
                                calculate_cidr: true
                                render_type: null
                                render_addr_mask: "public"
                                map_priority: 1
                                assign_vip: true
                              - name: "management"
                                cidr: "192.168.0.0/24"
                                vlan_start: 101
                                use_gateway: false
                                notation: "cidr"
                                render_type: "cidr"
                                render_addr_mask: "internal"
                                map_priority: 2
                                assign_vip: true
                              - name: "storage"
                                cidr: "192.168.1.0/24"
                                vlan_start: 102
                                use_gateway: false
                                notation: "cidr"
                                render_type: "cidr"
                                render_addr_mask: "storage"
                                map_priority: 2
                                assign_vip: false
                              - name: "private"
                                seg_type: "vlan"
                                vlan_start: null
                                use_gateway: false
                                notation: null
                                render_type: null
                                render_addr_mask: null
                                map_priority: 2
                                dedicated_nic: true
                                assign_vip: false
                            config:
                              parameters:
                                amqp:
                                  provider: "rabbitmq"
                                  username: null
                                  passwd: ""
                                  hosts: "hostname1:5672, hostname2:5672"
                                database:
                                  provider: "mysql"
                                  port: "3306"
                                  database: null
                                  username: null
                                  passwd:   ""
                                keystone:
                                  admin_user: null
                                  admin_password: ""
                                metadata:
                                  metadata_proxy_shared_secret: ""
                    - pk: 1
                      extend: *full_release
                      fields:
                        name: "CustomYamlFixtureRelease"
                        version: "2013.2.1"
                        operating_system: "CentOS"
                        description: "description"
                        attributes_metadata:
                          generated:
                            cobbler:
                              profile:
                                generator_arg: "centos-x86_64"
'''

        upload_fixture(cStringIO.StringIO(data), loader=yaml)
        check = self.db.query(Release).filter(
            Release.name == u"CustomYamlFixtureRelease"
        )
        self.assertEqual(len(list(check)), 1)

        release = list(check)[0]
        self.assertTrue(len(release.networks_metadata), 2)

    def test_yaml_json_fixtures(self):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        json_fixture = open('{0}/fixtures/model_fixture.json'.format(dir_path))
        upload_fixture(json_fixture, loader=json)
        yaml_fixture = open('{0}/fixtures/model_fixture.yaml'.format(dir_path))
        upload_fixture(yaml_fixture, loader=yaml)
        releases = self.db.query(Release).all()
        self.assertEqual(len(list(releases)), 2)

        attributes = ['networks_metadata', 'attributes_metadata',
                      'volumes_metadata', 'modes_metadata',
                      'roles_metadata', 'roles']

        for attr in attributes:
            diff = self.datadiff(getattr(releases[0], attr),
                                 getattr(releases[1], attr))
