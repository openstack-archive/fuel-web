#    Copyright 2016 Mirantis, Inc.
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
import netaddr
import yaml

from ..task import task

import nailgun.rpc as rpc

from nailgun import consts

from nailgun.db.sqlalchemy import models
from nailgun import errors
from nailgun.test.base import BaseIntegrationTest


class TestUpdateDnsmasqTaskManagers(BaseIntegrationTest):

    def setUp(self):
        super(TestUpdateDnsmasqTaskManagers, self).setUp()
        cluster = self.env.create(
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.gre},
            nodes_kwargs=[
                {'api': True,
                 'pending_addition': True}
            ]
        )
        self.cluster = self.db.query(models.Cluster).get(cluster['id'])

    def change_ip_range(self, net_name='fuelweb_admin', status_code=200):
        data = self.env.neutron_networks_get(self.cluster['id']).json_body
        admin = filter(lambda ng: ng['name'] == net_name,
                       data['networks'])[0]

        orig_range = netaddr.IPRange(admin['ip_ranges'][0][0],
                                     admin['ip_ranges'][0][1])
        admin['ip_ranges'][0] = [str(orig_range[0]), str(orig_range[-2])]

        resp = self.env.neutron_networks_put(
            self.cluster['id'], data, expect_errors=(status_code != 200))
        self.assertEqual(resp.status_code, status_code)
        return resp

    def test_update_dnsmasq_is_started_with_correct_message(self):
        message = {
            'api_version': '1',
            'method': 'execute_tasks',
            'respond_to': 'base_resp',
            'args': {
                'task_uuid': '',
                'tasks': [{
                    'type': consts.ORCHESTRATOR_TASK_TYPES.upload_file,
                    'uids': ['master'],
                    'parameters': {
                        'path': '/etc/hiera/networks.yaml',
                        'data': ''}
                }, {
                    'type': consts.ORCHESTRATOR_TASK_TYPES.puppet,
                    'uids': ['master'],
                    'parameters': {
                        'puppet_modules': '/etc/puppet/modules',
                        'puppet_manifest': '/etc/puppet/modules/fuel/'
                                           'examples/dhcp-ranges.pp',
                        'timeout': 300,
                        'cwd': '/'}
                }, {
                    'type': 'cobbler_sync',
                    'uids': ['master'],
                    'parameters': {
                        'provisioning_info': {
                            'engine': {
                                'url': 'http://localhost/cobbler_api',
                                'username': 'cobbler',
                                'password': 'cobbler',
                                'master_ip': '127.0.0.1'
                            }
                        }
                    }
                }]
            }
        }

        with mock.patch('nailgun.task.task.rpc.cast') as \
                mocked_task:
            self.change_ip_range()

            message['args']['tasks'][0]['parameters']['data'] = yaml.safe_dump(
                task.UpdateDnsmasqTask.get_admin_networks_data())
            update_task = self.db.query(models.Task).filter_by(
                name=consts.TASK_NAMES.update_dnsmasq).first()
            message['args']['task_uuid'] = update_task.uuid

            self.assertEqual(mocked_task.call_count, 1)
            self.assertEqual(mocked_task.call_args[0][1], message)

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_update_dnsmasq_started_and_completed(self, mocked_rpc):
        self.change_ip_range()
        self.assertEqual(mocked_rpc.call_count, 1)
        update_task = self.db.query(models.Task).filter_by(
            name=consts.TASK_NAMES.update_dnsmasq).first()
        self.assertEqual(update_task.status, consts.TASK_STATUSES.running)

        update_dnsmasq_msg = {
            "status": "ready",
            "task_uuid": update_task.uuid,
            "error": "",
            "msg": "Everything went fine."}

        rpc.receiver.NailgunReceiver.base_resp(**update_dnsmasq_msg)
        self.db.refresh(update_task)
        self.assertEqual(update_task.status, consts.TASK_STATUSES.ready)
        self.assertEqual(update_task.message, update_dnsmasq_msg['msg'])
        self.assertIsNone(update_task.deleted_at)

        # run it one more time
        self.change_ip_range()
        # rpc.cast was called one more time
        self.assertEqual(mocked_rpc.call_count, 2)
        update_tasks = self.db.query(models.Task).filter_by(
            name=consts.TASK_NAMES.update_dnsmasq)
        new_tasks = update_tasks.filter_by(status=consts.TASK_STATUSES.running)
        self.assertEqual(new_tasks.count(), 1)
        # old task was marked as deleted
        self.assertEqual(update_tasks.count(), 2)
        self.db.refresh(update_task)
        self.assertIsNotNone(update_task.deleted_at)

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_update_dnsmasq_started_and_failed(self, mocked_rpc):
        self.change_ip_range()
        self.assertEqual(mocked_rpc.call_count, 1)
        update_task = self.db.query(models.Task).filter_by(
            name=consts.TASK_NAMES.update_dnsmasq).first()
        self.assertEqual(update_task.status, consts.TASK_STATUSES.running)

        update_dnsmasq_msg = {
            "status": consts.TASK_STATUSES.error,
            "task_uuid": update_task.uuid,
            "error": "Something went wrong.",
            "msg": ""}

        rpc.receiver.NailgunReceiver.base_resp(**update_dnsmasq_msg)
        self.db.refresh(update_task)
        self.assertEqual(update_task.status, consts.TASK_STATUSES.error)
        self.assertEqual(update_task.message, update_dnsmasq_msg['error'])
        self.assertIsNone(update_task.deleted_at)

        # run it one more time
        self.change_ip_range()
        # rpc.cast was called one more time
        self.assertEqual(mocked_rpc.call_count, 2)
        update_tasks = self.db.query(models.Task).filter_by(
            name=consts.TASK_NAMES.update_dnsmasq)
        new_tasks = update_tasks.filter_by(status=consts.TASK_STATUSES.running)
        self.assertEqual(new_tasks.count(), 1)
        # old task was marked as deleted
        self.assertEqual(update_tasks.count(), 2)
        self.db.refresh(update_task)
        self.assertIsNotNone(update_task.deleted_at)

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_update_admin_failed_while_previous_in_progress(self, mocked_rpc):
        self.change_ip_range()
        self.assertEqual(mocked_rpc.call_count, 1)
        update_task = self.db.query(models.Task).filter_by(
            name=consts.TASK_NAMES.update_dnsmasq).first()
        self.assertEqual(update_task.status, consts.TASK_STATUSES.running)

        # change of other network works as it does not require to run
        # update_dnsmasq
        self.change_ip_range(net_name='public')
        # no more calls were made
        self.assertEqual(mocked_rpc.call_count, 1)

        # request was rejected as previous update_dnsmasq task is still
        # in progress
        resp = self.change_ip_range(status_code=409)
        self.assertEqual(resp.json_body['message'],
                         errors.UpdateDnsmasqTaskIsRunning.message)
        # no more calls were made
        self.assertEqual(mocked_rpc.call_count, 1)

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_update_dnsmasq_started_on_node_group_deletion(self, mocked_rpc):
        ng = self.env.create_node_group().json_body
        self.assertEqual(mocked_rpc.call_count, 0)

        self.env.delete_node_group(ng['id'])
        self.assertEqual(mocked_rpc.call_count, 1)
        update_task = self.db.query(models.Task).filter_by(
            name=consts.TASK_NAMES.update_dnsmasq).first()
        self.assertEqual(update_task.status, consts.TASK_STATUSES.running)
