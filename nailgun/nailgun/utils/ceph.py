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

    msg_templ = "osd_count={0}, pool_sz={1}, use_volumes={2}" + \
                " objects_ceph={3}, ephemeral_ceph={4}, images_ceph={5}"
    msg = msg_templ.format(osd_num, pool_sz, volumes_ceph, objects_ceph,
                           ephemeral_ceph, images_ceph)
    logger.debug("Estimating PG count " + msg)

    pre_7_0_pg_num = 2 ** int(math.ceil(math.log(osd_num * 100.0 / pool_sz, 2)))
    if emulate_pre_7_0:
        logger.debug("{'pg_num'}=" + str(pre_7_0_pg_num))
        return {'pg_num': pre_7_0_pg_num}

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
        if len(large_pools) + small_pool_count == 0:
            # no ceph used at all - fallback to pre_7.0
            logger.debug("{'pg_num'}=" + str(pre_7_0_pg_num))
            return {'pg_num': pre_7_0_pg_num}

        default_pg_count = total_pg_count / (len(large_pools)
                                             + small_pool_count)
        default_pg_count = max(minimal_pg_count, to_upper_power_two(default_pg_count))
        pg_per_weight = 0
    else:
        default_pg_count = max(minimal_pg_count,
                               to_upper_power_two(osd_num / pool_sz))
        pg_per_weight = ((total_pg_count - default_pg_count * small_pool_count)
                         / total_w)

    # pg_num is used for backward compatibility
    res = {'default_pg_num': default_pg_count}

    for pool in large_pools:
        calc_pg = to_upper_power_two(pool.weight * pg_per_weight)
        res[pool.name] = max(calc_pg, default_pg_count)

    for pool in LargePools.all_pools:
        res.setdefault(pool.name, int(default_pg_count))

    log_res = "{" + ",".join(map("{0[0]}={0[1]}".format, res.items())) + "}"
    logger.debug(log_res)

    return res
