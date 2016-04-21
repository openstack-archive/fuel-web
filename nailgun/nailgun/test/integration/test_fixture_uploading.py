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

import itertools
import mock
import os

from oslo_serialization import jsonutils
from six import StringIO
import yaml

from nailgun.db.sqlalchemy import fixman
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import Release
from nailgun import objects
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import DeploymentTasksTestMixin


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


class TestFixture(BaseIntegrationTest, DeploymentTasksTestMixin):

    fixtures = ['admin_network', 'sample_environment']
    maxDiff = None

    def test_upload_working(self):
        check = self.db.query(Node).all()
        self.assertEqual(len(list(check)), 8)

    def check_uploaded_tasks(self, fxtr_to_check_against, release_version):
        self.env.upload_fixtures(["openstack"])
        fxtr_path = os.path.join(fixman.get_base_fixtures_path(),
                                 fxtr_to_check_against)
        with open(fxtr_path) as f:
            deployment_tasks = yaml.load(f)

        fixman.load_fake_deployment_tasks(release_version)
        for rel in self.db.query(Release).all():
            deployment_graph = objects.DeploymentGraph.get_for_model(rel)
            db_deployment_tasks = objects.DeploymentGraph.get_tasks(
                deployment_graph)
            self._compare_tasks(deployment_tasks, db_deployment_tasks)

    def test_load_fake_deployment_tasks_for_90_release(self):
        self.check_uploaded_tasks('deployment_tasks_90.yaml', 'mitaka-9.0')

    def test_load_fake_deployment_tasks_by_default(self):
        # there is no deployment tasks fixture for 8.0 release so
        # those by default will be loaded (from 'deployment_tasks.yaml' file)
        self.check_uploaded_tasks('deployment_tasks.yaml', 'liberty-8.0')

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

    def test_get_fixture_for_release_fallback_to_default(self):
        # such release strings will cause IndexError to be raised inside
        # get_fixture_for_release function hence default fixtures file path
        # should be returned by it. 'Default' means that its name does not
        # bear version number in it
        incorrect_releases = ('2014.3', '-6')

        # if there is no fixture for given release file path
        # for default fixture file is returned either
        absent_releases = ('liberty-8.0', '2015.1.0-7.0')

        expected_fixture_path = os.path.join(
            fixman.get_base_fixtures_path(), 'deployment_tasks.yaml')

        for rel in itertools.chain(incorrect_releases, absent_releases):
            actual = fixman.get_fixture_for_release(
                rel, 'deployment_tasks', 'yaml')
            self.assertEqual(expected_fixture_path, actual)

    def test_get_fixture_for_release_90(self):
        expected = os.path.join(
            fixman.get_base_fixtures_path(), 'deployment_tasks_90.yaml')
        actual = fixman.get_fixture_for_release(
            'mitaka-9.0', 'deployment_tasks', 'yaml')
        self.assertEqual(expected, actual)
