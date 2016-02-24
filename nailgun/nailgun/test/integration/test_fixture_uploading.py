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

from nailgun import objects
from nailgun.db.sqlalchemy import fixman
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import Release
from nailgun.test.base import BaseDeploymentTasksTest
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


class TestFixture(BaseDeploymentTasksTest):

    fixtures = ['admin_network', 'sample_environment']
    maxDiff = None

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
            deployment_graph = objects.DeploymentGraph.get_for_model(rel)
            db_deployment_tasks = objects.DeploymentGraph.get_tasks(
                deployment_graph)
            self._compare_tasks(deployment_tasks, db_deployment_tasks)

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
