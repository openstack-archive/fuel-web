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

"""Ceph utils"""

import collections
import math


PG_COPY_PER_OSD = 200


Pool = collections.namedtuple("Pool", ['name', 'weight'])


class LargePools(object):
    cinder_volume = Pool('volumes', 16)
    compute = Pool('compute', 8)
    cinder_backup = Pool('backups', 4)
    rgw = Pool('.rgw', 4)
    glance = Pool('images', 1)
    all_pools = [cinder_volume, cinder_backup, rgw, compute, glance]


SMALL_RGW_POOL_COUNT = {
    'firefly': 4,
    'hammer': 12
}


def to_upper_power_two(val, threshold=1E-2):
    """round to next 2**X integer

    closest upper integer, which is power of two, treshold is for tolerating
    float errors
    """
    if val < threshold:
        return 0
    val_log2 = math.log(val, 2)
    return 2 ** int(val_log2 + (1 if val_log2 % 1 > threshold else 0))


def get_pool_pg_count(osd_num, pool_sz, ceph_version,
                      volumes_ceph, objects_ceph, ephemeral_ceph, images_ceph,
                      pg_per_osd=PG_COPY_PER_OSD,
                      emulate_pre_7_0=False,
                      minimal_pg_count=64):
    """calculate pg count for pools

    parametes:
        osd_num: int - OSD count
        pool_sz: int - pool size
        ceph_version:str - target ceph version - ["firefly","hammer"]
        volumes_ceph:bool - cinder volumes would be provided by ceph
        objects_ceph:bool - object storage would be provided by ceph
        ephemeral_ceph:bool - ephemeral disks would be provided by ceph
        images_ceph:bool - glance images storage would be provided by ceph
        pg_per_osd:int, default 200 - lower boundry of PG per OSD
        emulate_pre_7_0: bool, default False - simulate 6.1 behavoir
        minimal_pg_count: int, default 64 - minimal amout of PG per pool

    returns dictionary {pool_name: pool_pg_count}, with additional key -
    default_pg_num - default PG count for all pools, not in result
    """

    assert ceph_version in SMALL_RGW_POOL_COUNT,\
        "Unknown ceph version: {0}. Only {1} is supported".format(
            ceph_version, ", ".join(SMALL_RGW_POOL_COUNT))

    # * Estimated total amount of PG copyis calculated as
    #   (OSD * PG_COPY_PER_OSD),
    #   where PG_COPY_PER_OSD == 200 for now
    # * Each small pool gets one PG copy per OSD. Means (OSD / pool_sz) groups
    # * All the rest PG are devided between rest pools, proportional to their
    #   weights. By default next weights are used:

    #     volumes - 16
    #     compute - 8
    #     backups - 4
    #     .rgw - 4
    #     images - 1

    # * Each PG count is rounded to next power of 2

    if osd_num == 0:
        pre_7_0_pg_num = 128
    else:
        # pre 7.0 value
        pre_7_0_pg_num = 2 ** int(math.ceil(
            math.log(osd_num * 100.0 / pool_sz, 2)))

    res = {}
    for pool in LargePools.all_pools:
        res[pool.name] = int(pre_7_0_pg_num)

    res['default_pg_num'] = int(pre_7_0_pg_num)

    if emulate_pre_7_0 or osd_num == 0:
        return res

    osd_num = float(osd_num)
    total_pg_count = float(pg_per_osd) / pool_sz * osd_num
    large_pools = []
    small_pool_count = 0

    if volumes_ceph:
        large_pools.append(LargePools.cinder_volume)
        large_pools.append(LargePools.cinder_backup)
    if objects_ceph:
        small_pool_count += SMALL_RGW_POOL_COUNT[ceph_version]
        large_pools.append(LargePools.rgw)
    if ephemeral_ceph:
        large_pools.append(LargePools.compute)
    if images_ceph:
        large_pools.append(LargePools.glance)

    total_weight = sum(pool.weight for pool in large_pools)

    if total_weight == 0:
        if len(large_pools) + small_pool_count == 0:
            # no ceph used at all - fallback to pre_7.0
            return res

        default_pg_count = total_pg_count / (len(large_pools)
                                             + small_pool_count)
        default_pg_count = max(minimal_pg_count,
                               to_upper_power_two(default_pg_count))
        pg_per_weight = 0
    else:
        default_pg_count = max(minimal_pg_count,
                               to_upper_power_two(osd_num / pool_sz))
        pg_per_weight = ((total_pg_count
                          - default_pg_count * small_pool_count)
                         / total_weight)

        if pg_per_weight < 0:
            pg_per_weight = 0

    # reinit res
    res = {'default_pg_num': int(default_pg_count)}

    for pool in large_pools:
        calc_pg = to_upper_power_two(pool.weight * pg_per_weight)
        res[pool.name] = int(max(calc_pg, default_pg_count))

    for pool in LargePools.all_pools:
        res.setdefault(pool.name, int(default_pg_count))

    return res
