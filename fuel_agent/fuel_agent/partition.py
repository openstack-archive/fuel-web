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

from oslo.config import cfg
import stevedore.driver

from fuel_agent.utils import lvm_utils as lu
from fuel_agent.utils import md_utils as mu
from fuel_agent.utils import partition_utils as pu


opts = [
    cfg.StrOpt(
        'partition_parse_data_driver',
        default='ks_spaces',
        help='Parititoning parse data driver'
    ),
    cfg.StrOpt(
        'partition_get_data_driver',
        default='read_file',
        help='Parititoning get data driver'
    ),
]

CONF = cfg.CONF
CONF.register_opts(opts)


class PartitionManager(object):
    def __init__(self):
        data = stevedore.driver.DriverManager(
            namespace='fuel_agent.drivers',
            name=CONF.partition_get_data_driver).driver.get()

        self.scheme = stevedore.driver.DriverManager(
            namespace='fuel_agent.drivers',
            name=CONF.partition_parse_data_driver).driver.parse(data)

    def eval(self):
        for parted in self.scheme.parteds:
            pu.make_label(parted.name, parted.label)
            for prt in parted.partititons:
                pu.make_partition(prt.device, prt.begin, prt.end, prt.type)
                for flag in prt.flags:
                    pu.set_partition_flag(prt.device, prt.count, flag)

        # creating meta disks
        for md in self.scheme.mds:
            mu.mdcreate(md.name, md.level, *md.devices)

        # creating physical volumes
        for pv in self.scheme.pvs:
            lu.pvcreate(pv.name)

        # creating volume groups
        for vg in self.scheme.vgs:
            lu.vgcreate(vg.name, *vg.pvnames)

        # creating logical volumes
        for lv in self.scheme.lvs:
            lu.lvcreate(lv.vgname, lv.name, lv.size)

        # TODO(kozhukalov): create file systems
