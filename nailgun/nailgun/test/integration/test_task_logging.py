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
from nailgun.utils import reverse

from nailgun import consts
from nailgun import objects
from nailgun.statistics.fuel_statistics.tasks_params_white_lists \
    import task_output_white_list
from nailgun.task.helpers import TaskHelper


class TestTasksLogging(BaseIntegrationTest):

    def tearDown(self):
        self._wait_for_threads()
        super(TestTasksLogging, self).tearDown()

    def check_keys_included(self, keys, data):
        """Check that only values with keys from keys are present in data"""
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
        """Test task name against known value

        Check sanitized data doesn't contain keys which are absent in
        white_list

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
        deploy = self.env.launch_deployment()
        self.env.wait_ready(deploy)

        self.simulate_running_deployment(deploy)

        # FIXME(aroma): remove when stop action will be reworked for ha
        # cluster. To get more details, please, refer to [1]
        # [1]: https://bugs.launchpad.net/fuel/+bug/1529691
        cluster = self.env.clusters[0]
        objects.Cluster.set_deployed_before_flag(cluster, value=False)

        self.env.stop_deployment()

        self.assertGreaterEqual(len(logger.call_args_list), 1)
        self.check_task_name_and_sanitized_data(
            -1, logger, consts.TASK_NAMES.stop_deployment)

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

        logs = objects.ActionLogCollection.filter_by(
            None, action_type=consts.ACTION_TYPES.nailgun_task)
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

    def simulate_running_deployment(self, deploy_task, progress=42):
        """To exclude race condition errors in the tests we simulate deployment

        :param deploy_task: deploy task object
        :param progress: task progress value
        """
        # Updating deploy task
        TaskHelper.update_action_log(deploy_task)
        deploy_task.status = consts.TASK_STATUSES.running
        deploy_task.progress = progress
        # Updating action log
        action_log = objects.ActionLog.get_by_kwargs(
            task_uuid=deploy_task.uuid, action_name=deploy_task.name)
        action_log.end_timestamp = None

        self.db.commit()

    @fake_tasks()
    def test_update_task_logging_on_deployment(self):
        self.env.create(
            nodes_kwargs=[
                {"pending_addition": True, "pending_roles": ["controller"]}
            ]
        )
        deploy = self.env.launch_deployment()
        self.env.wait_ready(deploy)

        # Dereferencing uuid value due to deploy task deletion
        # after stop deployment
        deploy_uuid = deploy.uuid
        self.simulate_running_deployment(deploy)

        # FIXME(aroma): remove when stop action will be reworked for ha
        # cluster. To get more details, please, refer to [1]
        # [1]: https://bugs.launchpad.net/fuel/+bug/1529691
        cluster = self.env.clusters[0]
        objects.Cluster.set_deployed_before_flag(cluster, value=False)

        # Stopping deployment
        self.env.stop_deployment()

        # Checking action log updated
        action_log = objects.ActionLogCollection.filter_by(
            iterable=None, task_uuid=deploy_uuid).first()
        self.assertEqual(consts.TASK_NAMES.deploy, action_log.action_name)
        self.assertIsNotNone(action_log.end_timestamp)

    @fake_tasks()
    def test_update_task_logging_on_env_deletion(self):
        self.env.create(
            nodes_kwargs=[
                {"pending_addition": True, "pending_roles": ["controller"]}
            ]
        )
        deploy = self.env.launch_deployment()
        self.env.wait_ready(deploy)

        # Dereferencing uuid value due to deploy task deletion
        # after environment deletion
        deploy_uuid = deploy.uuid
        self.simulate_running_deployment(deploy)

        # Removing deployment
        self.env.delete_environment()

        # Checking action log updated
        action_log = objects.ActionLogCollection.filter_by(
            iterable=None, task_uuid=deploy_uuid).first()
        self.assertEqual(consts.TASK_NAMES.deploy, action_log.action_name)
        self.assertIsNotNone(action_log.end_timestamp)
