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

from nailgun.test.base import BaseTestCase

from nailgun import consts
from nailgun.objects import OpenStackWorkloadStats
from nailgun.objects import OpenStackWorkloadStatsCollection
from nailgun.settings import settings


class TestOSWLObject(BaseTestCase):

    def test_oswl_get_last_by_cluster_id_resource_type(self):
        cluster_id = 1
        dt = datetime.datetime.utcnow()
        obj_data = {
            'cluster_id': cluster_id,
            'resource_type': consts.OSWL_RESOURCE_TYPES.vm,

            'created_date': dt.date(),
            'updated_time': dt.time(),

            'resource_checksum': ""
        }
        obj = OpenStackWorkloadStats.create(obj_data)
        self.assertEqual(
            OpenStackWorkloadStats.get_last_by(
                cluster_id, consts.OSWL_RESOURCE_TYPES.vm),
            obj
        )
        self.assertIsNone(
            OpenStackWorkloadStats.get_last_by(
                0, consts.OSWL_RESOURCE_TYPES.vm)
        )
        self.assertIsNone(
            OpenStackWorkloadStats.get_last_by(
                cluster_id, consts.OSWL_RESOURCE_TYPES.tenant)
        )

        OpenStackWorkloadStats.delete(obj)
        self.assertIsNone(
            OpenStackWorkloadStats.get_last_by(
                cluster_id, consts.OSWL_RESOURCE_TYPES.vm)
        )

    def test_clean_expired_entries(self):
        dt_now = datetime.datetime.utcnow()
        t_delta = datetime.timedelta(days=settings.OSWL_STORING_PERIOD)

        entries_to_del_cluster_ids = (1, 2)
        for cluster_id in entries_to_del_cluster_ids:
            obj_kwargs = {
                "cluster_id": cluster_id,
                "resource_type": consts.OSWL_RESOURCE_TYPES.volume,
                "updated_time": dt_now.time(),
                "created_date": dt_now.date() - t_delta,
                "resource_checksum": ""
            }

            OpenStackWorkloadStats.create(obj_kwargs)

        untouched_obj_kwargs = {
            "cluster_id": 3,
            "resource_type": consts.OSWL_RESOURCE_TYPES.vm,
            "updated_time": dt_now.time(),
            "created_date": dt_now.date(),
            "resource_checksum": ""
        }
        OpenStackWorkloadStats.create(untouched_obj_kwargs)

        OpenStackWorkloadStatsCollection.clean_expired_entries()
        self.db.commit()

        for cluster_id in entries_to_del_cluster_ids:
            instance = \
                OpenStackWorkloadStats.get_last_by(
                    cluster_id,
                    consts.OSWL_RESOURCE_TYPES.volume
                )
            self.assertIsNone(instance)

        untouched_obj = OpenStackWorkloadStats.get_last_by(
            untouched_obj_kwargs["cluster_id"],
            consts.OSWL_RESOURCE_TYPES.vm
        )
        self.assertIsNotNone(untouched_obj)

    def test_version_info_serialized(self):
        version_info = {'release': '9.0'}
        dt = datetime.datetime.utcnow()
        obj = OpenStackWorkloadStats.create(
            {
                'cluster_id': 1,
                'resource_type': consts.OSWL_RESOURCE_TYPES.vm,
                'created_date': dt.date(),
                'updated_time': dt.time(),
                'resource_checksum': "",
                'version_info': version_info
            }
        )
        self.assertEqual(
            version_info,
            OpenStackWorkloadStats.to_dict(obj)['version_info']
        )
