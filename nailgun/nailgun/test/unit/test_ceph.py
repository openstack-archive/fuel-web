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

import math

from nailgun.test import base
from nailgun.utils import ceph


MAX_PG_PER_OSD = 600
MIN_PG_PER_OSD = 200
DEFAULT_PG = 128


class TestCephUtils(base.BaseUnitTest):
    def test_pg_count(self):
        params = [(osd, pool_sz, version,
                   dict(volumes_ceph=volumes_ceph,
                        objects_ceph=objects_ceph,
                        ephemeral_ceph=ephemeral_ceph,
                        images_ceph=images_ceph))
                  for osd in [0, 3, 20, 40, 100, 200, 1000, 5000]
                  for pool_sz in [1, 2, 3, 5]
                  for version in ['firefly', 'hammer']
                  for volumes_ceph in (True, False)
                  for objects_ceph in (True, False)
                  for ephemeral_ceph in (True, False)
                  for images_ceph in (True, False)]

        for osd, pool_sz, version, pools_used in params:
            if not any(pools_used.values()):
                continue

            res = ceph.get_pool_pg_count(osd, pool_sz, version,
                                         emulate_pre_7_0=False,
                                         **pools_used)

            old_res = ceph.get_pool_pg_count(osd, pool_sz,
                                             version,
                                             emulate_pre_7_0=True,
                                             **pools_used)

            if 0 == osd:
                self.assertEqual(res['default_pg_num'], DEFAULT_PG)
                self.assertEqual(old_res['default_pg_num'], DEFAULT_PG)
                continue

            pg_count = sum(res.values()) * pool_sz
            pg_count_lower_bound1 = osd * MAX_PG_PER_OSD
            pg_count_lower_bound2 = res['default_pg_num'] * len(res) * pool_sz

            if pg_count_lower_bound2 < pg_count_lower_bound1:
                self.assertLess(pg_count, pg_count_lower_bound1)

            if volumes_ceph or objects_ceph or ephemeral_ceph or images_ceph:
                self.assertGreater(pg_count, osd * MIN_PG_PER_OSD)

            pre_7_0_pg_num = 2 ** int(math.ceil(
                math.log(osd * 100.0 / pool_sz, 2)))

            self.assertEqual(old_res['default_pg_num'],
                             pre_7_0_pg_num)
