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


MAX_PG_PER_OSD = 400


class TestCephUtils(base.BaseUnitTest):
    def test_pg_count(self):
        params = [
            (3, 3, 'firefly',
             dict(volumes_ceph=True,
                  objects_ceph=True,
                  ephemeral_ceph=True,
                  images_ceph=True)),

            (20, 3, 'firefly',
             dict(volumes_ceph=True,
                  objects_ceph=True,
                  ephemeral_ceph=True,
                  images_ceph=True)),

            (200, 3, 'firefly',
             dict(volumes_ceph=True,
                  objects_ceph=True,
                  ephemeral_ceph=True,
                  images_ceph=True)),

            (40, 2, 'firefly',
             dict(volumes_ceph=True,
                  objects_ceph=False,
                  ephemeral_ceph=False,
                  images_ceph=False)),

            (100, 2, 'firefly',
             dict(volumes_ceph=True,
                  objects_ceph=True,
                  ephemeral_ceph=False,
                  images_ceph=True))]

        for osd, pool_sz, ver, pools_used in params:
            res = ceph.get_pool_pg_count(osd, pool_sz,
                                         ver, **pools_used)

            old_res = ceph.get_pool_pg_count(osd, pool_sz,
                                             ver,
                                             emulate_pre_7_0=True,
                                             **pools_used)
            summ = sum(res.values()) * pool_sz
            self.assertLess(summ, osd * MAX_PG_PER_OSD)

            pre_7_0_pg_num = 2 ** int(math.ceil(
                math.log(osd * 100.0 / pool_sz, 2)))

            self.assertEqual(old_res['default_pg_num'],
                             pre_7_0_pg_num)
