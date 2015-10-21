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

import mock
import os
from oslo_serialization import jsonutils
from six import StringIO
import yaml

from nailgun.db.sqlalchemy import fixman
from nailgun.db.sqlalchemy.models import Component
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import Release
from nailgun.db.sqlalchemy.models import ReleaseComponent
from nailgun.test.base import BaseIntegrationTest


class TestExtensionsCallback(BaseIntegrationTest):

    fixtures = ['admin_network', 'sample_environment']

    def setUp(self):
        # NOTE(eli): the method should be mocked before
        # setUp execution in parent class
        self.patcher = mock.patch(
            'nailgun.db.sqlalchemy.fixman.fire_callback_on_node_create')
        self.callback_mock = self.patcher.start()
        self.addCleanup(self.patcher.stop)
        super(TestExtensionsCallback, self).setUp()

    def test_upload_working(self):
        self.assertEqual(self.callback_mock.call_count, 8)


class TestFixture(BaseIntegrationTest):

    fixtures = ['admin_network', 'sample_environment']

    def test_upload_working(self):
        check = self.db.query(Node).all()
        self.assertEqual(len(list(check)), 8)

    def test_load_fake_deployment_tasks(self):
        self.env.upload_fixtures(["openstack"])
        fxtr_path = os.path.join(fixman.get_base_fixtures_path(),
                                 'deployment_tasks.yaml')
        with open(fxtr_path) as f:
            deployment_tasks = yaml.load(f)

        fixman.load_fake_deployment_tasks()

        for rel in self.db.query(Release).all():
            self.assertEqual(rel.deployment_tasks, deployment_tasks)

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

        fixman.upload_fixture(StringIO(data), loader=jsonutils)
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

        fixman.upload_fixture(StringIO(data), loader=yaml)
        check = self.db.query(Release).filter(
            Release.name == u"YAMLFixtureRelease"
        )
        self.assertEqual(len(list(check)), 1)
        check = self.db.query(Release).filter(
            Release.name == u"BaseRelease"
        )
        self.assertEqual(len(list(check)), 0)

    def test_load_component_fixtures(self):
        release_data = '''[{
            "pk": 1,
            "model": "nailgun.release",
            "fields": {
                "name": "FixtureRelease-1",
                "version": "0.0.1",
                "description": "Sample release for testing",
                "operating_system": "CentOS"
            }
        }, {
            "pk": 2,
            "model": "nailgun.release",
            "fields": {
                "name": "FixtureRelease-2",
                "version": "0.0.1",
                "description": "Sample release for testing",
                "operating_system": "Ubuntu"
            }
        }]'''
        fixman.upload_fixture(StringIO(release_data),
                              loader=jsonutils)
        db_release_ids = [r.id for r in self.db.query(Release).all()]

        sample_components = [{
            'type': 'hypervisor',
            'name': 'libvirt:kvm:exclusive',
            'release_ids': [db_release_ids[0]]
        }, {
            'type': 'storage',
            'name': 'object:backend:ceph',
            'release_ids': ['*']
        }]
        for sample_component in sample_components:
            expected_release_ids = sample_component['release_ids']
            if '*' in expected_release_ids:
                expected_release_ids = db_release_ids
            with mock.patch('yaml.load', return_value=[sample_component]):
                fixman.load_default_release_components()
                db_components = self.db.query(Component).filter_by(
                    name=sample_component['name'],
                    type=sample_component['type']
                ).all()
                self.assertEqual(len(db_components), 1)
                db_release_components = self.db.query(ReleaseComponent). \
                    filter_by(component_id=db_components[0].id).all()
                release_ids = [rc.release_id for rc in db_release_components]
                self.assertTrue(set(release_ids), set(expected_release_ids))

    def test_load_component_fixtures_for_wrong_releases(self):
        release_data = '''[{
            "pk": 1,
            "model": "nailgun.release",
            "fields": {
                "name": "JSONFixtureRelease",
                "version": "0.0.1",
                "description": "Sample release for testing",
                "operating_system": "CentOS"
            }
        }]'''
        fixman.upload_fixture(StringIO(release_data),
                              loader=jsonutils)
        release_id = self.db.query(Release).first().id
        component_data = [
            {
                'type': 'storage',
                'name': 'object:backend:ceph',
                'release_ids': [-1, release_id, release_id, 'x']
            },
            {
                'type': 'hypervisor',
                'name': 'libvirt:kvm',
                'release_ids': [release_id + 10, release_id + 11]
            }]
        with mock.patch('yaml.load', return_value=component_data):
            fixman.load_default_release_components()
            db_components = self.db.query(Component).filter_by(
                name=component_data[0]['name'],
                type=component_data[0]['type']
            ).all()
            self.assertEqual(len(db_components), 1)
            db_release_components = self.db.query(ReleaseComponent).filter_by(
                release_id=release_id,
                component_id=db_components[0].id
            ).all()
            self.assertEqual(len(db_release_components), 1)

    def test_load_component_fixtures_with_no_releases(self):
        fixman.load_default_release_components()
        self.assertEqual(len(self.db.query(Component).all()), 0)
        self.assertEqual(len(self.db.query(ReleaseComponent).all()), 0)
