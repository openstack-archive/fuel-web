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

import sys

from mock import patch

from nailgun.test.base import BaseTestCase

from nailgun import consts
from nailgun.objects import Cluster
from nailgun.objects import OpenStackWorkloadStats
from nailgun.statistics.oswl.collector import collect as oswl_collect_once
from nailgun.statistics.oswl.collector import run as run_collecting


class TestOSWLCollector(BaseTestCase):

    vms_info = [{
        "id": 1,
        "status": "running",
    }]

    def collect_for_operational_cluster(self, get_info_mock):
        cluster = self.env.create_cluster(
            api=False,
            status=consts.CLUSTER_STATUSES.operational
        )
        cls_id = cluster.id
        get_info_mock.return_value = self.vms_info
        oswl_collect_once(consts.OSWL_RESOURCE_TYPES.vm)
        last = OpenStackWorkloadStats.get_last_by(
            cls_id, consts.OSWL_RESOURCE_TYPES.vm)
        upd_time = last.updated_time
        res_data = {
            'added': [{'time': upd_time.isoformat(), 'id': 1}],
            'removed': [],
            'modified': [],
            'current': self.vms_info}
        self.assertEqual(last.resource_data, res_data)
        return cls_id, res_data

    def update_cluster_status_and_oswl_data(self, cls_id, status):
        cls = Cluster.get_by_uid(cls_id)
        Cluster.update(cls, {'status': status})
        oswl_collect_once(consts.OSWL_RESOURCE_TYPES.vm)
        return OpenStackWorkloadStats.get_last_by(
            cls_id, consts.OSWL_RESOURCE_TYPES.vm)

    @patch('nailgun.statistics.oswl.collector.utils.set_proxy')
    @patch('nailgun.statistics.oswl.collector.helpers.ClientProvider')
    @patch('nailgun.statistics.oswl.collector.helpers.'
           'get_info_from_os_resource_manager')
    def test_skip_collection_for_errorful_cluster(self, get_info_mock, *_):
        error_cluster_id = self.env.create(
            api=False,
            nodes_kwargs=[{"roles": ["controller"], "online": False}],
            cluster_kwargs={"name": "error",
                            "status": consts.CLUSTER_STATUSES.operational}
        ).id

        normal_cluster_id = self.env.create(
            api=False,
            nodes_kwargs=[{"roles": ["controller"], "online": True}],
            cluster_kwargs={"name": "normal",
                            "status": consts.CLUSTER_STATUSES.operational}
        ).id

        get_info_mock.return_value = self.vms_info

        oswl_collect_once(consts.OSWL_RESOURCE_TYPES.vm)

        last_for_error_clsr = OpenStackWorkloadStats.get_last_by(
            error_cluster_id, consts.OSWL_RESOURCE_TYPES.vm)
        self.assertIsNone(last_for_error_clsr)

        last_for_normal_clsr = OpenStackWorkloadStats.get_last_by(
            normal_cluster_id, consts.OSWL_RESOURCE_TYPES.vm)
        self.assertIsNotNone(last_for_normal_clsr)

        upd_time = last_for_normal_clsr.updated_time
        res_data = {
            'added': [{'time': upd_time.isoformat(), 'id': 1}],
            'removed': [],
            'modified': [],
            'current': self.vms_info}
        self.assertEqual(last_for_normal_clsr.resource_data, res_data)

    @patch('nailgun.statistics.oswl.collector.utils.get_proxy_for_cluster')
    @patch('nailgun.statistics.oswl.collector.utils.set_proxy')
    @patch('nailgun.statistics.oswl.collector.helpers.ClientProvider')
    @patch('nailgun.statistics.oswl.collector.helpers.'
           'get_info_from_os_resource_manager')
    def test_clear_data_for_changed_cluster(self, get_info_mock, *_):
        cls_id, res_data = self.collect_for_operational_cluster(get_info_mock)

        last = self.update_cluster_status_and_oswl_data(
            cls_id, consts.CLUSTER_STATUSES.error)
        # nothing is changed while cluster is in error status
        self.assertEqual(last.resource_data, res_data)

        last = self.update_cluster_status_and_oswl_data(
            cls_id, consts.CLUSTER_STATUSES.remove)
        removed = dict(self.vms_info[0])
        removed['time'] = last.updated_time.isoformat()
        res_data.update({
            'removed': [removed],
            'current': []})
        # current data is cleared when cluster status is changed
        self.assertEqual(last.resource_data, res_data)

    @patch('nailgun.statistics.oswl.collector.utils.get_proxy_for_cluster')
    @patch('nailgun.statistics.oswl.collector.utils.set_proxy')
    @patch('nailgun.statistics.oswl.collector.helpers.ClientProvider')
    @patch('nailgun.statistics.oswl.collector.helpers.'
           'get_info_from_os_resource_manager')
    def test_clear_data_for_removed_cluster(self, get_info_mock, *_):
        cls_id, res_data = self.collect_for_operational_cluster(get_info_mock)

        cls = Cluster.get_by_uid(cls_id)
        Cluster.delete(cls)

        oswl_collect_once(consts.OSWL_RESOURCE_TYPES.vm)
        last = OpenStackWorkloadStats.get_last_by(
            cls_id, consts.OSWL_RESOURCE_TYPES.vm)
        removed = dict(self.vms_info[0])
        removed['time'] = last.updated_time.isoformat()
        res_data.update({
            'removed': [removed],
            'current': []})
        # current data is cleared when cluster is deleted
        self.assertEqual(last.resource_data, res_data)

    @patch('nailgun.statistics.oswl.collector.utils.get_proxy_for_cluster')
    @patch('nailgun.statistics.oswl.collector.utils.set_proxy')
    @patch('nailgun.statistics.oswl.collector.helpers.ClientProvider')
    @patch('nailgun.statistics.oswl.collector.helpers.'
           'get_info_from_os_resource_manager')
    def test_removed_several_times(self, get_info_mock, *_):
        cls_id, res_data = self.collect_for_operational_cluster(get_info_mock)
        last = OpenStackWorkloadStats.get_last_by(
            cls_id, consts.OSWL_RESOURCE_TYPES.vm)
        self.assertItemsEqual(self.vms_info, last.resource_data['current'])

        # reset cluster
        get_info_mock.return_value = []
        oswl_collect_once(consts.OSWL_RESOURCE_TYPES.vm)
        last = OpenStackWorkloadStats.get_last_by(
            cls_id, consts.OSWL_RESOURCE_TYPES.vm)
        removed = dict(self.vms_info[0])
        removed['time'] = last.updated_time.isoformat()
        removed_data = [removed]
        # check data is not duplicated in removed on several collects
        for _ in xrange(10):
            oswl_collect_once(consts.OSWL_RESOURCE_TYPES.vm)
        last = OpenStackWorkloadStats.get_last_by(
            cls_id, consts.OSWL_RESOURCE_TYPES.vm)
        self.assertEqual(removed_data, last.resource_data['removed'])

        # cluster is operational
        # checking 'removed' is don't changed
        get_info_mock.return_value = self.vms_info
        oswl_collect_once(consts.OSWL_RESOURCE_TYPES.vm)
        last = OpenStackWorkloadStats.get_last_by(
            cls_id, consts.OSWL_RESOURCE_TYPES.vm)
        self.assertEqual(removed_data, last.resource_data['removed'])

        # reset cluster again
        # checking only id and time added to 'removed'
        get_info_mock.return_value = []
        oswl_collect_once(consts.OSWL_RESOURCE_TYPES.vm)
        last = OpenStackWorkloadStats.get_last_by(
            cls_id, consts.OSWL_RESOURCE_TYPES.vm)
        removed_data.append({
            'id': removed_data[0]['id'],
            'time': last.updated_time.isoformat()
        })
        self.assertListEqual(removed_data, last.resource_data['removed'])

    @patch("nailgun.statistics.oswl.collector.time.sleep",
           side_effect=StopIteration)
    @patch.object(sys, "argv", new=["_", consts.OSWL_RESOURCE_TYPES.vm])
    def test_oswl_is_not_collected_when_stats_collecting_disabled(self, *_):
        collect_func_path = ("nailgun.statistics.oswl.collector.collect")
        must_send_stats_path = ("nailgun.statistics.oswl.collector"
                                ".MasterNodeSettings.must_send_stats")

        with patch(must_send_stats_path, return_value=False):
            with patch(collect_func_path) as collect_mock:
                try:
                    run_collecting()
                except StopIteration:
                    pass

                self.assertFalse(collect_mock.called)

        with patch(must_send_stats_path, return_value=True):
            with patch(collect_func_path) as collect_mock:
                try:
                    run_collecting()
                except StopIteration:
                    pass

                self.assertTrue(collect_mock.called)
