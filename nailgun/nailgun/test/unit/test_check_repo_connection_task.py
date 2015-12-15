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

from nailgun import consts
from nailgun.db.sqlalchemy.models import Task
from nailgun.errors import errors
from nailgun.network.manager import NetworkManager
from nailgun import objects
from nailgun.task.task import CheckRepoAvailability
from nailgun.task.task import CheckRepoAvailabilityWithSetup
from nailgun.task.task import CheckRepositoryConnectionFromMasterNodeTask
from nailgun.test.base import BaseTestCase
from requests.exceptions import ConnectionError


@mock.patch('time.sleep')   # don't sleep on tests
class CheckRepositoryConnectionFromMasterNodeTaskTest(BaseTestCase):

    _response_error = mock.Mock(status_code=500, url='url1')
    _response_ok = mock.Mock(status_code=200, url='url1')

    _connection_error = ConnectionError()
    _connection_error.message = 'Connection aborted.'

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

    @mock.patch('requests.get', return_value=_response_ok)
    def test_execute_success(self, _, __):
        CheckRepositoryConnectionFromMasterNodeTask.execute(self.task)
        self.mrepos.assert_called_with(self.task.cluster)

    @mock.patch('requests.get', return_value=_response_error)
    def test_execute_fail(self, _, __):
        with self.assertRaises(errors.CheckBeforeDeploymentError) as cm:
            CheckRepositoryConnectionFromMasterNodeTask.execute(self.task)

        self.assertEqual(
            cm.exception.message,
            'Connection to following repositories could not be established: '
            '<url1 [500]>')

    @mock.patch('requests.get', side_effect=_connection_error)
    @mock.patch('nailgun.task.task.logger.error')
    def test_execute_fail_with_connection_error(self, m_error, _, __):
        with self.assertRaises(errors.CheckBeforeDeploymentError) as cm:
            CheckRepositoryConnectionFromMasterNodeTask.execute(self.task)

        m_error.assert_called_once_with(self._connection_error)
        self.assertEqual(
            cm.exception.message,
            "Connection to the repositories could not be "
            "established. Please refer to the Fuel Master "
            "web backend logs for more details.")

    @mock.patch('requests.get', side_effect=[_response_error, _response_ok])
    def test_execute_success_on_retry(self, _, __):
        CheckRepositoryConnectionFromMasterNodeTask.execute(self.task)
        self.mrepos.assert_called_with(self.task.cluster)


class TestRepoAvailability(BaseTestCase):

    def setUp(self):
        super(TestRepoAvailability, self).setUp()
        self.env.create(
            cluster_kwargs={
                'net_provider': 'neutron',
                'net_segment_type': 'gre'
            },
            nodes_kwargs=[{'roles': ['controller']},
                          {'roles': ['controller']},
                          {'roles': ['compute']},
                          {'roles': ['compute'], 'online': False}])

        self.cluster = self.env.clusters[0]
        self.public_ng = next(ng for ng in self.cluster.network_groups
                              if ng.name == 'public')
        self.free_ips = NetworkManager.get_free_ips(self.public_ng, 2)
        self.repo_urls = objects.Cluster.get_repo_urls(self.cluster)
        self.controllers = [n for n in self.cluster.nodes
                            if 'controller' in n.all_roles]
        self.online_uids = [n.uid for n in self.cluster.nodes if n.online]

    def test_repo_with_setup_generate_config(self):
        config, errors = CheckRepoAvailabilityWithSetup.get_config(
            self.cluster)
        self.assertEqual(len(config), 2)
        # resulted list of nodes contains only online uids
        self.assertTrue(
            set([n['uid'] for n in config]) <= set(self.online_uids))

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

    def test_nodes_to_check(self):
        task = objects.Task.create({
            'cluster': self.cluster,
            'name': consts.TASK_NAMES.check_repo_availability})
        repo_check = CheckRepoAvailability(task, {})
        self.assertItemsEqual(
            self.online_uids,
            [str(n['uid']) for n in repo_check._get_nodes_to_check()])
