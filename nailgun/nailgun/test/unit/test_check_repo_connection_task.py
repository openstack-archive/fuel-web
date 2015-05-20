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
from nailgun.network.manager import NetworkManager
from nailgun import objects
from nailgun.task.task import CheckRepositoryConnectionFromMasterNodeTask
from nailgun.task.task import CheckRepoAvailabilityWithSetup
from nailgun.test.base import BaseTestCase


class CheckRepositoryConnectionFromMasterNodeTaskTest(BaseTestCase):

    def setUp(self):
        super(CheckRepositoryConnectionFromMasterNodeTaskTest, self).setUp()
        self.env.create(
            cluster_kwargs={
                'net_provider': 'neutron',
                'net_segment_type': 'gre'
            },
            nodes_kwargs=[{'roles': ['controller']}])

        self.env.create_node()
        self.task = Task(cluster_id=self.env.clusters[0].id)
        self.env.db.add(self.task)
        self.env.db.flush()

        self.url = 'url1'
        self.mocked_repositories = [
            {'type': 'deb', 'uri': self.url, 'suite': 'suite'}]

        self.patcher = mock.patch(
            'nailgun.task.task.objects.Cluster.get_repo_urls',
            new=mock.Mock(return_value=self.mocked_repositories))
        self.mrepos = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        super(CheckRepositoryConnectionFromMasterNodeTaskTest, self).tearDown()

    @mock.patch('requests.get')
    def test_execute_success(self, get_mock):
        response_mock = mock.Mock()
        response_mock.status_code = 200
        response_mock.url = self.url
        get_mock.return_value = response_mock

        CheckRepositoryConnectionFromMasterNodeTask.execute(self.task)
        self.mrepos.assert_called_with(self.task.cluster)

    @mock.patch('requests.get')
    def test_execute_fail(self, get_mock):
        response_mock = mock.Mock()
        response_mock.status_code = 500
        response_mock.url = self.url
        get_mock.return_value = response_mock

        with self.assertRaises(errors.CheckBeforeDeploymentError):
            CheckRepositoryConnectionFromMasterNodeTask.execute(self.task)


class TestRepoAvailabilityWithSetup(BaseTestCase):

    def setUp(self):
        super(TestRepoAvailabilityWithSetup, self).setUp()
        self.env.create(
            cluster_kwargs={
                'net_provider': 'neutron',
                'net_segment_type': 'gre'
            },
            nodes_kwargs=[{'roles': ['controller']},
                          {'roles': ['controller']},
                          {'roles': ['compute']}])

        self.cluster = self.env.clusters[0]
        self.public_ng = next(ng for ng in self.cluster.network_groups
                              if ng.name == 'public')
        self.free_ips = NetworkManager.get_free_ips(self.public_ng, 2)
        self.repo_urls = objects.Cluster.get_repo_urls(self.cluster)
        self.controllers = [n for n in self.cluster.nodes
                            if 'controller' in n.all_roles]

    def test_generate_config(self):
        config, errors = CheckRepoAvailabilityWithSetup.get_config(
            self.cluster)
        self.assertEqual(len(config), 2)

        control_1, control_2 = self.controllers
        control_1_conf = next(c for c in config if c['uid'] == control_1.uid)
        control_2_conf = next(c for c in config if c['uid'] == control_2.uid)

        self.assertNotEqual(control_1_conf['addr'], control_2_conf['addr'])
        self.assertEqual(control_1_conf['gateway'], control_2_conf['gateway'])
        self.assertEqual(control_1_conf['gateway'], self.public_ng.gateway)
        self.assertIn(control_1_conf['addr'].split('/')[0], self.free_ips)
        self.assertIn(control_2_conf['addr'].split('/')[0], self.free_ips)

        self.assertEqual(control_1_conf['urls'], control_2_conf['urls'])
        self.assertEqual(control_1_conf['urls'], self.repo_urls)

        self.assertEqual(control_1_conf['vlan'], control_2_conf['vlan'])
