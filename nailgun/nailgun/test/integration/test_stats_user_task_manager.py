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

from oslo.serialization import jsonutils

from nailgun import consts
from nailgun import objects
from nailgun.test.base import BaseMasterNodeSettignsTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


class TestStatsUserTaskManagers(BaseMasterNodeSettignsTest):

    @fake_tasks(override_state={'progress': 100,
                                'status': consts.TASK_STATUSES.ready})
    def test_create_stats_user(self):
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['controller'], 'pending_addition': True},
            ]
        )

        deploy_task = self.env.launch_deployment()
        self.env.wait_ready(deploy_task)

        with mock.patch('nailgun.objects.MasterNodeSettings.must_send_stats',
                        return_value=True):
            resp = self.app.patch(
                reverse('MasterNodeSettingsHandler'),
                headers=self.default_headers,
                params=jsonutils.dumps({})
            )
            self.assertEqual(200, resp.status_code)

        task = objects.TaskCollection.filter_by(
            None, name=consts.TASK_NAMES.create_stats_user).first()
        self.assertIsNotNone(task)
        self.env.wait_ready(task)

    @fake_tasks(override_state={'progress': 100,
                                'status': consts.TASK_STATUSES.ready})
    def test_no_tasks_duplication(self):
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
            ]
        )

        deploy_task = self.env.launch_deployment()
        self.env.wait_ready(deploy_task)

        task_count_before = objects.TaskCollection.filter_by(
            None, name=consts.TASK_NAMES.create_stats_user).count()

        with mock.patch('nailgun.objects.MasterNodeSettings.must_send_stats',
                        return_value=True):
            with mock.patch('nailgun.task.fake.settings.'
                            'FAKE_TASKS_TICK_INTERVAL', 10):
                resp = self.app.patch(
                    reverse('MasterNodeSettingsHandler'),
                    headers=self.default_headers,
                    params='{}'
                )
                self.assertEqual(200, resp.status_code)

                resp = self.app.patch(
                    reverse('MasterNodeSettingsHandler'),
                    headers=self.default_headers,
                    params='{}'
                )
                self.assertEqual(200, resp.status_code)

        task_count = objects.TaskCollection.filter_by(
            None, name=consts.TASK_NAMES.create_stats_user).count()
        self.assertEqual(task_count_before + 1, task_count)

    @fake_tasks(override_state={'progress': 100,
                                'status': consts.TASK_STATUSES.ready})
    def test_no_tasks_for_non_operational_clusters(self):
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
            ]
        )

        deploy_task = self.env.launch_deployment()
        self.env.wait_ready(deploy_task)

        cluster = self.env.clusters[0]
        with mock.patch('nailgun.objects.MasterNodeSettings.must_send_stats',
                        return_value=True):
            for cluster_status in consts.CLUSTER_STATUSES:
                if cluster_status == consts.CLUSTER_STATUSES.operational:
                    continue

                cluster.status = cluster_status
                self.env.db().flush()

                resp = self.app.patch(
                    reverse('MasterNodeSettingsHandler'),
                    headers=self.default_headers,
                    params='{}'
                )
                self.assertEqual(200, resp.status_code)

                task_count = objects.TaskCollection.filter_by(
                    None, name=consts.TASK_NAMES.create_stats_user).count()
                self.assertEqual(0, task_count)

    def test_create_stats_user_not_required(self):
        with mock.patch('nailgun.objects.MasterNodeSettings.must_send_stats',
                        return_value=False):
            with mock.patch('nailgun.task.manager.CreateStatsUserTaskManager.'
                            'execute') as executer:
                resp = self.app.patch(
                    reverse('MasterNodeSettingsHandler'),
                    headers=self.default_headers,
                    params=jsonutils.dumps({})
                )
                self.assertEqual(200, resp.status_code)
                self.assertFalse(executer.called)

    def test_create_stats_user_called(self):
        with mock.patch('nailgun.objects.MasterNodeSettings.must_send_stats',
                        return_value=True):
            with mock.patch('nailgun.task.manager.CreateStatsUserTaskManager.'
                            'execute') as executer:
                resp = self.app.patch(
                    reverse('MasterNodeSettingsHandler'),
                    headers=self.default_headers,
                    params=jsonutils.dumps({})
                )
                self.assertEqual(200, resp.status_code)
                self.assertTrue(executer.called)
