import math
import collections

from nailgun.logger import logger


PG_COPY_PER_OSD = 200


Pool = collections.namedtuple("Pool", ['name', 'weight'])


class LargePools(object):
    cinder_volume = Pool('volumes', 16)
    compute = Pool('compute', 8)
    cinder_backup = Pool('backups', 4)
    rgw = Pool('.rgw', 4)
    glance = Pool('images', 1)
    all_pools = [cinder_volume, cinder_backup, rgw, compute, glance]


def to_upper_power_two(val, threshold=1E-2):
    val_log2 = math.log(val, 2)
    return 2 ** int(val_log2 + (1 if val_log2 % 1 > threshold else 0))


SMALL_RGW_POOL_COUNT = {
    'firefly': 4,
    'hammer': 12
}


def get_pool_pg_count(osd_num, pool_sz, ceph_version,
                      volumes_ceph, objects_ceph, ephemeral_ceph, images_ceph,
                      pg_per_osd=200, emulate_pre_7_0=False,
                      minimal_pg_count=64):
    """
    calculate pg count for pools
    """
    # * Estimated total amount of PG copyes calculated as
    #   (OSD * PG_COPY_PER_OSD),
    #   where PG_COPY_PER_OSD == 200 for now
    # * Each small pool get one PG copy per OSD. Means (OSD / pool_sz) groups
    # * All the rest PG are devided between rest pools, proportional to it
    #   weights. By default next weights are used:

    #     volumes - 16
    #     compute - 8
    #     backups - 4
    #     .rgw - 4
    #     images - 1

    # * Each PG count is rounded to next power of 2

    msg_templ = "osd_count={0}, pool_sz={1}, use_volumes={2}" + \
                " objects_ceph={3}, ephemeral_ceph={4}, images_ceph={5}"
    msg = msg_templ.format(osd_num, pool_sz, volumes_ceph, objects_ceph,
                           ephemeral_ceph, images_ceph)
    logger.debug("Estimating PG count " + msg)

    if emulate_pre_7_0:
        pg_num = 2 ** int(math.ceil(math.log(osd_num * 100.0 / pool_sz, 2)))
        logger.debug("{'pg_num'}=" + str(pg_num))
        return {'pg_num': pg_num}

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

    total_w = sum(pool.weight for pool in large_pools)

    if total_w == 0:
        default_size = total_pg_count / (len(LargePools.all_pools)
                                         + small_pool_count)
        default_size = max(minimal_pg_count, to_upper_power_two(default_size))
    else:
        default_size = max(minimal_pg_count,
                           to_upper_power_two(osd_num / pool_sz))
        pg_per_weight = ((total_pg_count - default_size * small_pool_count)
                         / total_w)

    # pg_num is used for backward compatibility
    res = {'pg_num': default_size}

    if pg_per_weight > 1:
        for pool in large_pools:
            res[pool.name] = to_upper_power_two(pool.weight * pg_per_weight)

    for pool in LargePools.all_pools:
        res.setdefault(pool.name, int(default_size))

    log_res = "{" + ",".join(map("{0[0]}={0[1]}".format, res.items())) + "}"
    logger.debug(log_res)

    return res
