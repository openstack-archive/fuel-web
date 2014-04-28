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

from collections import OrderedDict as odict

from nailgun.logger import logger


class RaidType:
    RAID0 = 0
    RAID1 = 1
    RAID5 = 5
    RAID10 = 10


RAID_DISKS_COUNT = {RaidType.RAID0: (1, 16),
                    RaidType.RAID1: (2, 80),
                    RaidType.RAID5: (3, 16),
                    RaidType.RAID10: (4, 16)}


NODE_TO_RAID_ROLES = {
    'controller': odict([('root', ('/', RaidType.RAID1)),
                        ('mysql', ('/var/lib/mysql', RaidType.RAID10)),
                        ('glance-cache',
                            ('/var/lib/images-cache', RaidType.RAID5))]),
    'compute': odict([('root', ('/', 1)),
                      ('virt-storage',
                          ('/var/lib/nova', RaidType.RAID10))]),
}


class RaidManager(object):

    @classmethod
    def get_default_raid_configuration(cls, node):
        """Return default RAID configuration for given node
        based on RAID controllers and drives information in
        metadata
        """
        raid_config = {}

        if len(node.pending_roles) == 0:
            # no roles assigned to node, so nothing to
            # configure
            logger.debug("node %s has no roles assigned, no raid config",
                         node.id)
            return raid_config

        raid_info = node.meta.get('raid')
        if not raid_info:
            # no RAIDs, nothing to configure
            logger.debug("node %s has no raid info in metadata, skip config",
                         node.id)
            return raid_config

        if len(raid_info["controllers"]) == 0:
            # no controllers
            logger.debug("node %s has no raid controllers, skip config",
                         node.id)
            return raid_config

        # for now, work only with the first controller
        try:
            avail_physical_drives = \
                raid_info["controllers"][0]["physical_drives"][:]
            product_name = raid_info["controllers"][0]["vendor"]
        except KeyError:
            logger.debug("node %s has malformed raid info", node.id)
            return raid_config

        if len(avail_physical_drives) == 0:
            # no disks, nothing to do
            logger.debug("node %s has no physical disks in raid contoller",
                         node.id)
            return raid_config
        elif len(avail_physical_drives) == 1:
            # only one disk, create a JBOD for / and finish
            eid = avail_physical_drives[0]["enclosure"]
            phys_id = avail_physical_drives[0]["slot"]
            raid_config["raid_model"] = product_name
            root_jbod = {"mount_point": "/",
                         "raid_idx": 0,
                         "raid_lvl": "jbod",
                         "phys_devices": [phys_id],
                         "ctrl_id": raid_info["controllers"][0][
                             "controller_id"],
                         "eid": eid,
                         "raid_name": "RAID JBOD"}
            raid_config["raids"] = [root_jbod]
            return raid_config

        created_roles = []

        raid_config['raids'] = []
        raid_config['raid_model'] = product_name

        raid_idx = 0
        for node_role in node.pending_roles:
            raid_roles = NODE_TO_RAID_ROLES[node_role]
            for raid_role, raid_props in raid_roles.items():
                # role already configured, skip
                if raid_role in created_roles:
                    continue

                required_drives = RAID_DISKS_COUNT[raid_props[1]][0]
                if len(avail_physical_drives) >= required_drives:
                    phys_devs = []
                    for i in range(required_drives):
                        phys_devs.append(avail_physical_drives.pop())
                    eid = phys_devs[0]["enclosure"]
                    phys_devs_ids = [dev['slot'] for dev in phys_devs]
                    raid_name = 'RAID %s for %s' % (raid_props[1], raid_role)
                    ctrl_id = raid_info["controllers"][0]["controller_id"]
                    raid_config['raids'].append({'mount_point': raid_props[0],
                                                 'raid_idx': raid_idx,
                                                 'raid_lvl': raid_props[1],
                                                 'phys_devices': phys_devs_ids,
                                                 'ctrl_id': ctrl_id,
                                                 'eid': eid,
                                                 'raid_name': raid_name})
                    created_roles.append(raid_role)
                    raid_idx += 1
                else:
                    break

        return raid_config
