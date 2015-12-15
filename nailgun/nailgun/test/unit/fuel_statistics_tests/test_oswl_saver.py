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


import datetime
import six

from nailgun.statistics import utils
from nailgun.test.base import BaseTestCase

from nailgun import consts
from nailgun.objects import OpenStackWorkloadStats
from nailgun.objects import OpenStackWorkloadStatsCollection
from nailgun.statistics.oswl.saver import oswl_data_checksum
from nailgun.statistics.oswl.saver import oswl_statistics_save


class TestOSWLServerInfoSaving(BaseTestCase):

    vms_info = {
        "id": 1,
        "status": "running",
        "power_state": 1,
        "created_at": "dt",
        "host_id": "111",
        "tenant_id": "222",
        "image_id": "333",
        "flavor_id": "444"
    }

    @property
    def empty_data(self):
        return {
            'cluster_id': 1,
            'resource_type': consts.OSWL_RESOURCE_TYPES.vm,
            'created_date': datetime.datetime.utcnow().date(),

            'resource_data': {'added': [],
                              'removed': [],
                              'modified': [],
                              'current': []},
            'resource_checksum': oswl_data_checksum([]),
            'is_sent': False
        }

    def data_w_default_vm_info(self, time):
        data = self.empty_data
        data['resource_data'].update({
            'added': [{'time': time.isoformat(), 'id': 1}],
            'current': [self.vms_info]
        })
        return data

    def check_overall_rec_count(self, count):
        saved = OpenStackWorkloadStatsCollection.all()
        self.assertEqual(saved.count(), count)
        return saved

    def check_data_vs_rec(self, data, rec):
        data['resource_checksum'] = \
            oswl_data_checksum(data['resource_data']['current'])
        for k, v in six.iteritems(data):
            if isinstance(v, (list, tuple)):
                self.assertItemsEqual(v, getattr(rec, k))
            else:
                self.assertEqual(v, getattr(rec, k))

    def save_data_and_check_record(self, data):
        oswl_statistics_save(1, consts.OSWL_RESOURCE_TYPES.vm, data)
        last = OpenStackWorkloadStats.get_last_by(
            1, consts.OSWL_RESOURCE_TYPES.vm)
        self.assertEqual(last, self.check_overall_rec_count(1).first())
        return last

    def add_default_vm_info_and_check(self):
        last = self.save_data_and_check_record([self.vms_info])
        time_update = last.updated_time
        data = self.data_w_default_vm_info(time_update)
        self.check_data_vs_rec(data, last)
        return time_update, data

    def test_empty_data(self):
        last = self.save_data_and_check_record([])
        self.check_data_vs_rec(self.empty_data, last)

    def test_added_same_info(self):
        # VM is added
        time_update, data = self.add_default_vm_info_and_check()

        # save same info
        last = self.save_data_and_check_record([self.vms_info])
        # DB row was not updated
        self.assertEqual(time_update, last.updated_time)
        self.check_data_vs_rec(data, last)

    def test_added_one_by_one(self):
        # VM with id=1 is added
        time_update1, data = self.add_default_vm_info_and_check()

        # VM with id=2 is added
        two_vms = [dict(self.vms_info), dict(self.vms_info)]
        two_vms[1]['id'] = 2
        last = self.save_data_and_check_record(two_vms)

        time_update2 = last.updated_time
        data['resource_data'].update({
            'added': [{'time': time_update1.isoformat(), 'id': 1},
                      {'time': time_update2.isoformat(), 'id': 2}],
            'current': two_vms
        })
        self.check_data_vs_rec(data, last)

    def test_added_on_cluster_reset(self):
        # VM with id=1 is added
        time_update1, data = self.add_default_vm_info_and_check()

        # VM with id=2 is added
        two_vms = [self.vms_info]

        self.save_data_and_check_record(two_vms)
        # reset cluster
        self.save_data_and_check_record([])
        last = self.save_data_and_check_record(two_vms)

        time_update2 = last.updated_time
        time_removed2 = last.resource_data['removed'][0]['time']
        data['resource_data'].update({
            'added': [{'time': time_update1.isoformat(), 'id': 1},
                      {'time': time_update2.isoformat(), 'id': 1}],
            'current': two_vms,
            'removed': [dict(two_vms[0], **{'time': time_removed2})]
        })
        self.check_data_vs_rec(data, last)

    def test_added_then_removed(self):
        # VM is added
        time_update, data = self.add_default_vm_info_and_check()

        # VM is removed
        last = self.save_data_and_check_record([])

        time_update = last.updated_time
        removed = dict(self.vms_info)
        removed['time'] = time_update.isoformat()
        data['resource_data'].update({
            'removed': [removed],
            'current': []
        })
        self.check_data_vs_rec(data, last)

    def test_modified(self):
        # VM is added
        time_update, data = self.add_default_vm_info_and_check()

        # VM power state and status are changed
        vms_new = [dict(self.vms_info)]
        vms_new[0]['power_state'] = 0
        vms_new[0]['status'] = 'stopped'
        last = self.save_data_and_check_record(vms_new)

        time_update = last.updated_time
        modified1 = {'power_state': self.vms_info['power_state'],
                     'status': self.vms_info['status'],
                     'time': time_update.isoformat(),
                     'id': self.vms_info['id']}
        data['resource_data'].update({
            'modified': [modified1],
            'current': vms_new
        })
        self.check_data_vs_rec(data, last)

        # VM power state is changed back
        vms_new1 = [dict(vms_new[0])]
        vms_new1[0]['power_state'] = 1
        last = self.save_data_and_check_record(vms_new1)

        time_update = last.updated_time
        modified2 = {'power_state': vms_new[0]['power_state'],
                     'time': time_update.isoformat(),
                     'id': vms_new[0]['id']}
        data['resource_data'].update({
            'modified': [modified1, modified2],
            'current': vms_new1
        })
        self.check_data_vs_rec(data, last)

        # VM status is changed back
        last = self.save_data_and_check_record([self.vms_info])

        time_update = last.updated_time
        modified3 = {'status': vms_new1[0]['status'],
                     'time': time_update.isoformat(),
                     'id': vms_new1[0]['id']}
        data['resource_data'].update({
            'modified': [modified1, modified2, modified3],
            'current': [self.vms_info]
        })
        self.check_data_vs_rec(data, last)

    def test_add_row_per_day(self):
        # VM is added
        last = self.save_data_and_check_record([self.vms_info])

        date_cur = last.created_date
        time_update = last.updated_time
        date_1st_rec = date_cur - datetime.timedelta(days=1)
        # make existing record one day older
        OpenStackWorkloadStats.update(last,
                                      {'created_date': date_1st_rec})

        # pass the same data
        # no new record was created and existing one remains unchanged
        self.assertEqual(last,
                         self.save_data_and_check_record([self.vms_info]))

        # VM is removed
        oswl_statistics_save(1, consts.OSWL_RESOURCE_TYPES.vm, [])
        saved = self.check_overall_rec_count(2)
        last = OpenStackWorkloadStats.get_last_by(
            1, consts.OSWL_RESOURCE_TYPES.vm)

        self.assertEqual(last.created_date, date_cur)
        for rec in saved:
            if rec.created_date == date_cur:
                self.assertEqual(rec, last)
                # last record contains 'removed' and empty 'added'
                data = self.empty_data
                removed = dict(self.vms_info)
                removed['time'] = last.updated_time.isoformat()
                data['resource_data']['removed'] = [removed]
                self.check_data_vs_rec(data, rec)
            elif rec.created_date == date_1st_rec:
                # first record contains 'added' and empty 'removed'
                data = self.data_w_default_vm_info(time_update)
                data['created_date'] = date_1st_rec
                self.check_data_vs_rec(data, rec)

    def test_oswl_is_sent_restored_on_changes(self):
        cluster_id = 1
        vm_info = {
            "id": 1,
            "power_state": 1,
        }
        oswl_statistics_save(cluster_id, consts.OSWL_RESOURCE_TYPES.vm,
                             [vm_info])
        last = OpenStackWorkloadStats.get_last_by(
            cluster_id, consts.OSWL_RESOURCE_TYPES.vm)
        # Setting is_sent to True
        OpenStackWorkloadStats.update(last, {'is_sent': True})
        self.assertEqual(True, last.is_sent)

        # Checking is_sent is not changed if data is not changed
        oswl_statistics_save(cluster_id, consts.OSWL_RESOURCE_TYPES.vm,
                             [vm_info])
        last_no_change = OpenStackWorkloadStats.get_last_by(
            cluster_id, consts.OSWL_RESOURCE_TYPES.vm)
        self.assertEqual(True, last_no_change.is_sent)

        # Checking is_sent is changed if data is changed
        vm_info["power_state"] += 1
        oswl_statistics_save(cluster_id, consts.OSWL_RESOURCE_TYPES.vm,
                             [vm_info])
        last_changed = OpenStackWorkloadStats.get_last_by(
            cluster_id, consts.OSWL_RESOURCE_TYPES.vm)
        self.assertEqual(False, last_changed.is_sent)

    def test_oswl_statistics_save_version_info(self):
        self.env.create()
        cluster = self.env.clusters[0]

        # Without version info
        oswl_statistics_save(cluster.id, consts.OSWL_RESOURCE_TYPES.vm, [])
        oswl = OpenStackWorkloadStats.get_last_by(
            cluster.id, consts.OSWL_RESOURCE_TYPES.vm)
        self.assertEqual({}, oswl.version_info)

        # With version info
        oswl_statistics_save(
            cluster.id, consts.OSWL_RESOURCE_TYPES.vm, [{'id': 1}],
            version_info=utils.get_version_info(cluster)
        )
        oswl = OpenStackWorkloadStats.get_last_by(
            cluster.id, consts.OSWL_RESOURCE_TYPES.vm)
        self.assertEqual(utils.get_version_info(cluster), oswl.version_info)
