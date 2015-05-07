# -*- coding: utf-8 -*-
#    Copyright 2015 Mirantis, Inc.
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

from nailgun.db.sqlalchemy.models import Task
from nailgun.errors import errors
from nailgun.task.task import CheckRepositoryConnectionTask
from nailgun.test.base import BaseTestCase


class CheckRepositoryConnectionTaskTest(BaseTestCase):

    def setUp(self):
        super(CheckRepositoryConnectionTaskTest, self).setUp()
        self.env.create(
            cluster_kwargs={
                'net_provider': 'neutron',
                'net_segment_type': 'gre'
            },
            nodes_kwargs=[{'roles': ['controller']}])

        self.env.create_node()
        self.node = self.env.nodes[0]
        self.cluster = self.env.clusters[0]
        self.task = Task(cluster_id=self.env.clusters[0].id)
        self.env.db.add(self.task)
        self.env.db.commit()

        self.url = 'url1'
        self.mocked_repositories = [
            {'type': 'deb', 'uri': self.url, 'suite': 'suite'}]

        self.test_url = CheckRepositoryConnectionTask._add_test_url(
            self.mocked_repositories[0])['test_url']

    @mock.patch('requests.get')
    def test_execute_success(self, get_mock):
        response_mock = mock.Mock()
        response_mock.status_code = 200
        response_mock.url = self.url
        get_mock.return_value = response_mock

        CheckRepositoryConnectionTask._get_repository_list = mock.Mock(
            return_value=self.mocked_repositories)

        CheckRepositoryConnectionTask.execute(self.task)

        CheckRepositoryConnectionTask._get_repository_list.assert_called_with(
            self.task
        )

    @mock.patch('requests.get')
    def test_execute_fail(self, get_mock):
        response_mock = mock.Mock()
        response_mock.status_code = 500
        response_mock.url = self.test_url
        get_mock.return_value = response_mock

        CheckRepositoryConnectionTask._get_repository_list = mock.Mock(
            return_value=self.mocked_repositories)

        with self.assertRaises(errors.CheckBeforeDeploymentError):
            CheckRepositoryConnectionTask.execute(self.task)
