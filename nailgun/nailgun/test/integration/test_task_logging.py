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
from nailgun import objects
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
            self.assertIn(keys, ("", {}))

    def check_task_name_and_sanitized_data(self, pos, logger, task_name,
                                           one_parameter=False):
        """Test task name against known value and check sanitized data doesn't
        contain keys which are absent in white_list.

        :param pos: position of call parameters inside logger.call_args_list,
                    (negative value: -1 - last call, -2 - pre-last call, etc.)
        :param logger: mock object for logger method
        :param task_name: expected task name
        :param one_parameter: whether given call must go with one parameter
        """
        log_args = logger.call_args_list
        task = log_args[pos][0][0]
        self.assertEqual(task.name, task_name)
        if len(log_args[pos][0]) == 2:
            log_record = log_args[pos][0][1]
            if task_name in task_output_white_list:
                self.check_keys_included(
                    task_output_white_list[task_name],
                    TaskHelper.sanitize_task_output(task.cache, log_record))
            else:
                self.assertIsNone(
                    TaskHelper.sanitize_task_output(task.cache, log_record))
        else:
            self.assertTrue(one_parameter)

    @fake_tasks(god_mode=True)
    @patch.object(TaskHelper, 'update_action_log')
    def test_deployment_task_logging(self, logger):
        self.env.create(
            cluster_kwargs={
                'net_provider': 'neutron',
                'net_segment_type': 'gre'
            },
            nodes_kwargs=[
                {"pending_addition": True, "pending_roles": ["controller"]},
                {"pending_addition": True, "pending_roles": ["cinder"]},
                {"pending_addition": True, "pending_roles": ["compute"]},
            ]
        )
        supertask = self.env.launch_deployment()

        self.assertEqual(len(logger.call_args_list), 6)
        self.check_task_name_and_sanitized_data(
            -6, logger, consts.TASK_NAMES.check_networks)
        self.check_task_name_and_sanitized_data(
            -5, logger, consts.TASK_NAMES.check_networks, one_parameter=True)
        self.check_task_name_and_sanitized_data(
            -4, logger, consts.TASK_NAMES.check_before_deployment)
        self.check_task_name_and_sanitized_data(
            -3, logger, consts.TASK_NAMES.check_before_deployment,
            one_parameter=True)
        self.check_task_name_and_sanitized_data(
            -2, logger, consts.TASK_NAMES.provision)
        self.check_task_name_and_sanitized_data(
            -1, logger, consts.TASK_NAMES.deployment)

        self.env.wait_ready(supertask, 15)

        # call for 'deploy' is added
        self.assertEqual(len(logger.call_args_list), 7)
        self.check_task_name_and_sanitized_data(
            -1, logger, consts.TASK_NAMES.deploy, one_parameter=True)

    @fake_tasks(god_mode=True)
    @patch.object(TaskHelper, 'update_action_log')
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
    @patch.object(TaskHelper, 'update_action_log')
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
    @patch.object(TaskHelper, 'update_action_log')
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
    @patch.object(TaskHelper, 'update_action_log')
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
    @patch.object(TaskHelper, 'update_action_log')
    def test_dump_task_logging(self, logger):
        resp = self.app.put(
            reverse('LogPackageHandler'), headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 202)

        self.assertGreaterEqual(len(logger.call_args_list), 1)
        self.check_task_name_and_sanitized_data(
            -1, logger, consts.TASK_NAMES.dump)

    @fake_tasks(god_mode=True)
    @patch.object(TaskHelper, 'update_action_log')
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

    @fake_tasks(god_mode=True)
    def test_deployment_tasks_records(self):
        self.env.create(
            cluster_kwargs={
                'net_provider': 'neutron',
                'net_segment_type': 'gre'
            },
            nodes_kwargs=[
                {"pending_addition": True, "pending_roles": ["controller"]},
                {"pending_addition": True, "pending_roles": ["cinder"]},
                {"pending_addition": True, "pending_roles": ["compute"]},
            ]
        )
        supertask = self.env.launch_deployment()
        self.env.wait_ready(supertask, 15)

        logs = objects.ActionLogCollection.all()
        self.assertEqual(5, logs.count())
        for log in logs:
            self.assertIsNotNone(log.end_timestamp)
            self.assertIsNotNone(log.additional_info)
            add_info = log.additional_info
            self.assertEqual(add_info["ended_with_status"],
                             consts.TASK_STATUSES.ready)
            if add_info["output"]:
                TestTasksLogging().check_keys_included(
                    task_output_white_list[log.action_name],
                    add_info["output"]
                )
                self.assertIn(log.action_name,
                              (consts.TASK_NAMES.deployment,
                               consts.TASK_NAMES.provision))
            else:
                self.assertIn(log.action_name,
                              (consts.TASK_NAMES.deploy,
                               consts.TASK_NAMES.check_networks,
                               consts.TASK_NAMES.check_before_deployment))
