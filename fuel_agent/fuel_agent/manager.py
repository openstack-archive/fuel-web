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

import os

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
    cfg.StrOpt(
        'nc_template_path',
        default='/usr/share/fuel-agent/cloud-init-templates',
        help='Path to directory with cloud init templates',
    ),
    cfg.StrOpt(
        'nc_cc_ubuntu_name',
        default='cloud_config_ubuntu.jinja2',
        help='Ubuntu cloud config template name',
    ),
    cfg.StrOpt(
        'nc_bh_ubuntu_name',
        default='boothook_ubuntu.jinja2',
        help='Ubuntu boothook template name',
    ),
    cfg.StrOpt(
        'tmp_path',
        default='/tmp',
        help='Temporary directory for file manipulations',
    ),
    cfg.StrOpt(
        'config_drive_path',
        default='/tmp/config-drive.img',
        help='Path where to store generated config drive image',
    ),
]

CONF = cfg.CONF
CONF.register_opts(opts)


class Manager(object):
    def __init__(self, data):
        self.data = utils.get_driver(CONF.data_driver)(data)

    def do_partitioning(self):
        scheme = self.data.partitioning_scheme()
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
        nc_data = self.data.nocloud_data
        tmpl_dir = CONF.nc_template_path
        cc_output_path = os.path.join(CONF.tmp_path, 'cloud_config.txt')
        bh_output_path = os.path.join(CONF.tmp_path, 'boothook.txt')
        # NOTE:file should be strictly named as 'user-data'
        # TODO(agordeev): add centos support
        ud_output_path = os.path.join(CONF.tmp_path, 'user-data')
        utils.render_and_save(tmpl_dir, CONF.nc_cc_ubuntu_name,

                             nc_data.config_drive, cc_output_path)
        utils.render_and_save(tmpl_dir, CONF.nc_bh_ubuntu_name,
                             nc_data.boothook, bh_output_path)

        utils.execute('write-mime-multipart', '--output=%s' % ud_output_path,
                      '%s:text/cloud-boothook' % bh_output_path,
                      '%s:text/cloud-config' % cc_output_path)
        utils.execute('genisoimage', '-output', CONF.config_drive_path,
                      '-volid', 'cidata', '-joliet', '-rock', ud_output_path)

    def do_copyimage(self):
        img_data = self.data.img_data
        for img in img_data:
            utils.deploy_image(img.src, img.dst, img.dd_extra_opts)

    def do_bootloader(self):
        pass

    def do_provisioning(self):
        self.do_partitioning()
        self.do_configdrive()
        self.do_copyimage()
        self.do_bootloader()
