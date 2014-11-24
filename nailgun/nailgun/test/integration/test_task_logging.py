# -*- coding: utf-8 -*-

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


from mock import patch

from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse

from nailgun import consts
from nailgun.statistics.params_white_lists import task_output_white_list
from nailgun.task.helpers import TaskHelper


class TestTasksLogging(BaseIntegrationTest):

    def tearDown(self):
        self._wait_for_threads()
        super(TestTasksLogging, self).tearDown()

    def check_keys_included(self, keys, data):
        """Check that only values with keys from 'keys' are present in 'data'
        """
        if isinstance(data, list):
            for d in data:
                self.check_keys_included(keys, d)
        elif isinstance(data, dict):
            for k in data:
                if k in keys:
                    self.check_keys_included(keys[k], data[k])
                elif "*" in keys:
                    self.check_keys_included(keys["*"], data[k])
                else:
                    self.fail("key {0} is not present in {1}".format(k, keys))
        else:
            self.assertEqual("", keys)

    def check_task_name_and_sanitized_data(self, pos, logger, task_name):
        log_args = logger.call_args_list
        task = log_args[pos][0][0]
        log_record = log_args[pos][0][1]
        self.assertEqual(task.name, task_name)
        self.check_keys_included(
            task_output_white_list[task_name],
            TaskHelper.sanitize_task_output(task.cache, log_record))

    @fake_tasks(god_mode=True)
    @patch('nailgun.task.manager.TaskManager.update_action_log')
    def test_deployment_task_logging(self, logger):
        self.env.create(
            nodes_kwargs=[
                {"pending_addition": True, "pending_roles": ["controller"]},
                {"pending_addition": True, "pending_roles": ["cinder"]},
                {"pending_addition": True, "pending_roles": ["compute"]},
                {"pending_deletion": True, "pending_roles": ["compute"]},
            ]
        )
        supertask = self.env.launch_deployment()
        self.env.wait_ready(supertask, 15)

        self.assertGreaterEqual(len(logger.call_args_list), 3)
        self.check_task_name_and_sanitized_data(
            -3, logger, consts.TASK_NAMES.node_deletion)
        self.check_task_name_and_sanitized_data(
            -2, logger, consts.TASK_NAMES.provision)
        self.check_task_name_and_sanitized_data(
            -1, logger, consts.TASK_NAMES.deployment)

    @fake_tasks(god_mode=True)
    @patch('nailgun.task.manager.TaskManager.update_action_log')
    def test_delete_task_logging(self, logger):
        self.env.create(
            nodes_kwargs=[
                {"roles": ["controller"]},
                {"roles": ["cinder"]},
                {"roles": ["compute"]},
            ]
        )
        self.env.delete_environment()

        self.assertGreaterEqual(len(logger.call_args_list), 1)
        self.check_task_name_and_sanitized_data(
            -1, logger, consts.TASK_NAMES.cluster_deletion)

    @fake_tasks(god_mode=True)
    @patch('nailgun.task.manager.TaskManager.update_action_log')
    def test_reset_task_logging(self, logger):
        self.env.create(
            nodes_kwargs=[
                {"roles": ["controller"]},
                {"roles": ["cinder"]},
                {"roles": ["compute"]},
            ]
        )
        self.env.reset_environment()

        self.assertGreaterEqual(len(logger.call_args_list), 1)
        self.check_task_name_and_sanitized_data(
            -1, logger, consts.TASK_NAMES.reset_environment)

    @fake_tasks(god_mode=True, recover_nodes=False)
    @patch('nailgun.task.manager.TaskManager.update_action_log')
    def test_stop_task_logging(self, logger):
        self.env.create(
            nodes_kwargs=[
                {"pending_addition": True, "pending_roles": ["controller"]},
                {"pending_addition": True, "pending_roles": ["cinder"]},
                {"pending_addition": True, "pending_roles": ["compute"]},
            ]
        )
        self.env.launch_deployment()
        self.env.stop_deployment()

        self.assertGreaterEqual(len(logger.call_args_list), 1)
        self.check_task_name_and_sanitized_data(
            -1, logger, consts.TASK_NAMES.stop_deployment)

    @fake_tasks(god_mode=True)
    @patch('nailgun.task.manager.TaskManager.update_action_log')
    def test_update_task_logging(self, logger):
        self.env.create(
            nodes_kwargs=[
                {"roles": ["controller"], "status": "ready"},
                {"roles": ["cinder"], "status": "ready"},
                {"roles": ["compute"], "status": "ready"},
            ]
        )
        self.env.update_environment()

        self.assertGreaterEqual(len(logger.call_args_list), 1)
        self.check_task_name_and_sanitized_data(
            -1, logger, consts.TASK_NAMES.update)

    @fake_tasks(god_mode=True)
    @patch('nailgun.task.manager.TaskManager.update_action_log')
    def test_dump_task_logging(self, logger):
        resp = self.app.put(
            reverse('LogPackageHandler'), "[]", headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 202)

        self.assertGreaterEqual(len(logger.call_args_list), 1)
        self.check_task_name_and_sanitized_data(
            -1, logger, consts.TASK_NAMES.dump)

    @fake_tasks(god_mode=True)
    @patch('nailgun.task.manager.TaskManager.update_action_log')
    def test_verify_task_logging(self, logger):
        self.env.create(
            nodes_kwargs=[
                {"pending_addition": True, "pending_roles": ["controller"]},
                {"pending_addition": True, "pending_roles": ["cinder"]},
                {"pending_addition": True, "pending_roles": ["compute"]},
            ]
        )
        self.env.launch_verify_networks()

        self.assertGreaterEqual(len(logger.call_args_list), 1)
        self.check_task_name_and_sanitized_data(
            -1, logger, consts.TASK_NAMES.verify_networks)
