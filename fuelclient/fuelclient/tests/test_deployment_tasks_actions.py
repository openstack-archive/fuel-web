# -*- coding: utf-8 -*-
#
#    Copyright 2014 Mirantis, Inc.
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

import json
import os

from mock import patch

from fuelclient.tests import base


API_INPUT = [{'id': 'primary-controller'}]
API_OUTPUT = '- id: primary-controller\n'
RELEASE_OUTPUT = [{'id': 1, 'version': '2014.2-6.0', 'name': 'Something'}]
MULTIPLE_RELEASES = [{'id': 1, 'version': '2014.2-6.0', 'name': 'Something'},
                     {'id': 2, 'version': '2014.3-6.1', 'name': 'Something'}]


@patch('fuelclient.client.requests')
@patch('fuelclient.cli.serializers.open', create=True)
@patch('fuelclient.cli.actions.base.os')
class TestReleaseDeploymentTasksActions(base.UnitTestCase):

    def test_release_tasks_download(self, mos, mopen, mrequests):
        mrequests.get().json.return_value = API_INPUT
        self.execute_wo_auth(
            ['fuel', 'rel', '--rel', '1', '--deployment-tasks', '--download'])
        mopen().__enter__().write.assert_called_once_with(API_OUTPUT)

    def test_release_tasks_upload(self, mos, mopen, mrequests):
        mopen().__enter__().read.return_value = API_OUTPUT
        self.execute_wo_auth(
            ['fuel', 'rel', '--rel', '1', '--deployment-tasks', '--upload'])
        self.assertEqual(mrequests.put.call_count, 1)
        call_args = mrequests.put.call_args_list[0]
        url = call_args[0][0]
        kwargs = call_args[1]
        self.assertIn('releases/1/deployment_tasks', url)
        self.assertEqual(
            json.loads(kwargs['data']), API_INPUT)


@patch('fuelclient.client.requests')
@patch('fuelclient.cli.serializers.open', create=True)
@patch('fuelclient.cli.actions.base.os')
class TestClusterDeploymentTasksActions(base.UnitTestCase):

    def test_cluster_tasks_download(self, mos, mopen, mrequests):
        mrequests.get().json.return_value = API_INPUT
        self.execute_wo_auth(
            ['fuel', 'env', '--env', '1', '--deployment-tasks', '--download'])
        mopen().__enter__().write.assert_called_once_with(API_OUTPUT)

    def test_cluster_tasks_upload(self, mos, mopen, mrequests):
        mopen().__enter__().read.return_value = API_OUTPUT
        self.execute_wo_auth(
            ['fuel', 'env', '--env', '1', '--deployment-tasks', '--upload'])
        self.assertEqual(mrequests.put.call_count, 1)
        call_args = mrequests.put.call_args_list[0]
        url = call_args[0][0]
        kwargs = call_args[1]
        self.assertIn('clusters/1/deployment_tasks', url)
        self.assertEqual(
            json.loads(kwargs['data']), API_INPUT)


@patch('fuelclient.client.requests')
@patch('fuelclient.cli.serializers.open', create=True)
@patch('fuelclient.cli.utils.iterfiles')
class TestSyncDeploymentTasks(base.UnitTestCase):

    def test_sync_deployment_scripts(self, mfiles, mopen, mrequests):
        mrequests.get().json.return_value = RELEASE_OUTPUT
        mfiles.return_value = ['/etc/puppet/2014.2-6.0/tasks.yaml']
        mopen().__enter__().read.return_value = API_OUTPUT

        self.execute_wo_auth(
            ['fuel', 'rel', '--sync-deployment-tasks'])

        mfiles.assert_called_once_with(
            os.path.realpath(os.curdir), ('tasks.yaml',))

        call_args = mrequests.put.call_args_list[0]
        url = call_args[0][0]
        kwargs = call_args[1]
        self.assertIn('releases/1/deployment_tasks', url)
        self.assertEqual(
            json.loads(kwargs['data']), API_INPUT)

    def test_sync_with_directory_path(self, mfiles, mopen, mrequests):
        mrequests.get().json.return_value = RELEASE_OUTPUT
        mfiles.return_value = ['/etc/puppet/2014.2-6.0/tasks.yaml']
        mopen().__enter__().read.return_value = API_OUTPUT
        real_path = '/etc/puppet'
        self.execute_wo_auth(
            ['fuel', 'rel', '--sync-deployment-tasks', '--dir', real_path])
        mfiles.assert_called_once_with(real_path, ('tasks.yaml',))

    def test_multiple_tasks_but_one_release(self, mfiles, mopen, mrequests):
        mrequests.get().json.return_value = RELEASE_OUTPUT
        mfiles.return_value = ['/etc/puppet/2014.2-6.0/tasks.yaml',
                               '/etc/puppet/2014.3-6.1/tasks.yaml']
        mopen().__enter__().read.return_value = API_OUTPUT

        self.execute_wo_auth(
            ['fuel', 'rel', '--sync-deployment-tasks'])

        self.assertEqual(mrequests.put.call_count, 1)

    def test_multiple_releases(self, mfiles, mopen, mrequests):
        mrequests.get().json.return_value = MULTIPLE_RELEASES
        mfiles.return_value = ['/etc/puppet/2014.2-6.0/tasks.yaml',
                               '/etc/puppet/2014.3-6.1/tasks.yaml']
        mopen().__enter__().read.return_value = API_OUTPUT

        self.execute_wo_auth(
            ['fuel', 'rel', '--sync-deployment-tasks'])

        self.assertEqual(mrequests.put.call_count, 2)
