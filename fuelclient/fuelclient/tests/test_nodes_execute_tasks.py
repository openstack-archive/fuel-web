# -*- coding: utf-8 -*-
#
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

import json

from mock import patch

from fuelclient.tests import base


@patch('fuelclient.client.requests')
class TestNodeExecuteTasksAction(base.UnitTestCase):

    def test_execute_provided_list_of_tasks(self, mrequests):
        tasks = ['netconfig', 'hiera']

        self.execute(
            ['fuel', 'node', '--node', '1,2', '--env', '5', '--tasks'] + tasks)
        kwargs = mrequests.put.call_args_list[0][1]
        self.assertEqual(json.loads(kwargs['data']), tasks)

    @patch('fuelclient.objects.environment.Environment.get_deployment_tasks')
    def test_skipped_tasks(self, get_tasks, mrequests):
        tasks = ['netconfig', 'hiera', 'install']
        get_tasks.return_value = [{'id': t} for t in tasks]
        self.execute(
            ['fuel', 'node', '--node', '1,2',
             '--env', '5', '--skip'] + tasks[:2])

        kwargs = mrequests.put.call_args_list[0][1]
        self.assertEqual(json.loads(kwargs['data']), tasks[2:])

    @patch('fuelclient.objects.environment.Environment.get_deployment_tasks')
    def test_end_task(self, get_tasks, mrequests):
        tasks = ['netconfig', 'hiera', 'install']
        get_tasks.return_value = [{'id': t} for t in tasks]
        self.execute(
            ['fuel', 'node', '--node', '1,2',
             '--env', '5', '--end', tasks[-1]])
        kwargs = mrequests.put.call_args_list[0][1]
        self.assertEqual(json.loads(kwargs['data']), tasks)

    @patch('fuelclient.objects.environment.Environment.get_deployment_tasks')
    def test_skip_with_end_task(self, get_tasks, mrequests):
        tasks = ['netconfig', 'hiera', 'install']
        get_tasks.return_value = [{'id': t} for t in tasks]
        self.execute(
            ['fuel', 'node', '--node', '1,2',
             '--env', '5', '--end', tasks[-1], '--skip'] + tasks[:2])

        kwargs = mrequests.put.call_args_list[0][1]
        self.assertEqual(json.loads(kwargs['data']), tasks[2:])
