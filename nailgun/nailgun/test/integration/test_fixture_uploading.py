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
import yaml

from nailgun.db.sqlalchemy.fixman import upload_fixture
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import Release
from nailgun.openstack.common import jsonutils
from nailgun.test.base import BaseIntegrationTest


class TestFixture(BaseIntegrationTest):

    fixtures = ['admin_network', 'sample_environment']

    def test_upload_working(self):
        check = self.db.query(Node).all()
        self.assertEqual(len(list(check)), 8)

    def test_json_fixture(self):
        data = '''[{
            "pk": 2,
            "model": "nailgun.release",
            "fields": {
                "name": "JSONFixtureRelease",
                "version": "0.0.1",
                "description": "Sample release for testing",
                "operating_system": "CentOS"
            }
        }]'''

        upload_fixture(cStringIO.StringIO(data), loader=jsonutils)
        check = self.db.query(Release).filter(
            Release.name == u"JSONFixtureRelease"
        )
        self.assertEqual(len(list(check)), 1)

    def test_yaml_fixture(self):
        data = '''---
- &base_release
  model: nailgun.release
  fields:
    name: BaseRelease
    version: 0.0.1
    operating_system: AbstractOS
- pk: 2
  extend: *base_release
  fields:
    name: YAMLFixtureRelease
    version: 1.0.0
    operating_system: CentOS
'''

        upload_fixture(cStringIO.StringIO(data), loader=yaml)
        check = self.db.query(Release).filter(
            Release.name == u"YAMLFixtureRelease"
        )
        self.assertEqual(len(list(check)), 1)
        check = self.db.query(Release).filter(
            Release.name == u"BaseRelease"
        )
        self.assertEqual(len(list(check)), 0)

    def test_fixture_roles_order(self):
        data = '''[{
            "pk": 1,
            "model": "nailgun.release",
            "fields": {
                "name": "CustomFixtureRelease1",
                "version": "0.0.1",
                "description": "Sample release for testing",
                "operating_system": "CentOS",
                "roles": ["controller", "compute", "cinder", "ceph-osd"]
            }
        }]'''
        upload_fixture(cStringIO.StringIO(data), loader=jsonutils)
        rel = self.db.query(Release).filter(
            Release.name == u"CustomFixtureRelease1"
        ).all()
        self.assertEqual(len(rel), 1)
        self.assertEqual(list(rel[0].roles),
                         ["controller", "compute", "cinder", "ceph-osd"])

        data = '''[{
            "pk": 2,
            "model": "nailgun.release",
            "fields": {
                "name": "CustomFixtureRelease2",
                "version": "0.0.1",
                "description": "Sample release for testing",
                "operating_system": "CentOS",
                "roles": ["compute", "ceph-osd", "controller", "cinder"]
            }
        }]'''
        upload_fixture(cStringIO.StringIO(data), loader=jsonutils)
        rel = self.db.query(Release).filter(
            Release.name == u"CustomFixtureRelease2"
        ).all()
        self.assertEqual(len(rel), 1)
        self.assertEqual(list(rel[0].roles),
                         ["compute", "ceph-osd", "controller", "cinder"])

        data = '''[{
            "pk": 3,
            "model": "nailgun.release",
            "fields": {
                "name": "CustomFixtureRelease3",
                "version": "0.0.1",
                "description": "Sample release for testing",
                "operating_system": "CentOS",
                "roles": ["compute", "cinder", "controller", "cinder"]
            }
        }]'''
        upload_fixture(cStringIO.StringIO(data), loader=jsonutils)
        rel = self.db.query(Release).filter(
            Release.name == u"CustomFixtureRelease3"
        ).all()
        self.assertEqual(len(rel), 1)
        self.assertEqual(list(rel[0].roles),
                         ["compute", "cinder", "controller"])
        # check previously added release roles
        prev_rel = self.db.query(Release).filter(
            Release.name == u"CustomFixtureRelease2"
        ).all()
        self.assertEqual(len(prev_rel), 1)
        self.assertEqual(list(prev_rel[0].roles),
                         ["compute", "ceph-osd", "controller", "cinder"])
