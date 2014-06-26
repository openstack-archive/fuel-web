# Copyright 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json

from oslo.config import cfg

from fuel_agent.utils import fs_utils as fu
from fuel_agent.utils import lvm_utils as lu
from fuel_agent.utils import md_utils as mu
from fuel_agent.utils import partition_utils as pu
from fuel_agent.utils import utils

opts = [
    cfg.StrOpt(
        'data_driver',
        default='nailgun',
        help='Data driver'
    ),
]

CONF = cfg.CONF
CONF.register_opts(opts)


class Manager(object):
    def __init__(self, data):
        self.data = utils.get_driver(CONF.data_driver)(data)

    def do_partitioning(self):
        scheme = self.data.partitioning_scheme
        for parted in scheme.parteds:
            pu.make_label(parted.name, parted.label)
            for prt in parted.partititons:
                pu.make_partition(prt.device, prt.begin, prt.end, prt.type)
                for flag in prt.flags:
                    pu.set_partition_flag(prt.device, prt.count, flag)

        # creating meta disks
        for md in scheme.mds:
            mu.mdcreate(md.name, md.level, *md.devices)

        # creating physical volumes
        for pv in scheme.pvs:
            lu.pvcreate(pv.name)

        # creating volume groups
        for vg in scheme.vgs:
            lu.vgcreate(vg.name, *vg.pvnames)

        # creating logical volumes
        for lv in scheme.lvs:
            lu.lvcreate(lv.vgname, lv.name, lv.size)

        # making file systems
        for fs in scheme.fss:
            fu.make_fs(fs.type, fs.options, fs.label, fs.device)

    def do_configdrive(self):
        pass

    def do_copyimage(self):
        pass

    def do_bootloader(self):
        pass

    def do_provisioning(self):
        self.do_partitioning()
        self.do_configdrive()
        self.do_copyimage()
        self.do_bootloader()