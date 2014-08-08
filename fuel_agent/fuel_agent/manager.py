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

from fuel_agent import errors
from fuel_agent.utils import artifact_utils as au
from fuel_agent.utils import fs_utils as fu
from fuel_agent.utils import grub_utils as gu
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
        self.driver = utils.get_driver(CONF.data_driver)(data)
        self.partition_scheme = None
        self.configdrive_scheme = None
        self.image_scheme = None

    def do_parsing(self):
        self.partition_scheme = self.driver.partition_scheme()
        self.configdrive_scheme = self.driver.configdrive_scheme()
        self.image_scheme = self.driver.image_scheme(self.partition_scheme)

    def do_partitioning(self):
        for parted in self.partition_scheme.parteds:
            pu.make_label(parted.name, parted.label)
            for prt in parted.partitions:
                pu.make_partition(prt.device, prt.begin, prt.end, prt.type)
                for flag in prt.flags:
                    pu.set_partition_flag(prt.device, prt.count, flag)

        # creating meta disks
        for md in self.partition_scheme.mds:
            mu.mdcreate(md.name, md.level, *md.devices)

        # creating physical volumes
        for pv in self.partition_scheme.pvs:
            lu.pvcreate(pv.name)

        # creating volume groups
        for vg in self.partition_scheme.vgs:
            lu.vgcreate(vg.name, *vg.pvnames)

        # creating logical volumes
        for lv in self.partition_scheme.lvs:
            lu.lvcreate(lv.vgname, lv.name, lv.size)

        # making file systems
        for fs in self.partition_scheme.fss:
            fu.make_fs(fs.type, fs.options, fs.label, fs.device)

    def do_configdrive(self):
        cc_output_path = os.path.join(CONF.tmp_path, 'cloud_config.txt')
        bh_output_path = os.path.join(CONF.tmp_path, 'boothook.txt')
        # NOTE:file should be strictly named as 'user-data'
        #      the same is for meta-data as well
        ud_output_path = os.path.join(CONF.tmp_path, 'user-data')
        md_output_path = os.path.join(CONF.tmp_path, 'meta-data')

        tmpl_dir = CONF.nc_template_path
        utils.render_and_save(
            tmpl_dir, self.configdrive_scheme.template_name('cloud_config'),
            self.configdrive_scheme.template_data(), cc_output_path
        )
        utils.render_and_save(
            tmpl_dir, self.configdrive_scheme.template_name('boothook'),
            self.configdrive_scheme.template_data(), bh_output_path
        )
        utils.render_and_save(
            tmpl_dir, self.configdrive_scheme.template_name('meta-data'),
            self.configdrive_scheme.template_data(), md_output_path
        )

        utils.execute('write-mime-multipart', '--output=%s' % ud_output_path,
                      '%s:text/cloud-boothook' % bh_output_path,
                      '%s:text/cloud-config' % cc_output_path)
        utils.execute('genisoimage', '-output', CONF.config_drive_path,
                      '-volid', 'cidata', '-joliet', '-rock', ud_output_path,
                      md_output_path)

        configdrive_device = self.partition_scheme.configdrive_device()
        if configdrive_device is None:
            raise errors.WrongPartitionSchemeError(
                'Error while trying to get configdrive device: '
                'configdrive device not found')
        self.image_scheme.add_image(
            uri='file://%s' % CONF.config_drive_path,
            target_device=configdrive_device,
            image_format='iso9660',
            container='raw'
        )

    def do_copyimage(self):
        for image in self.image_scheme.images:
            processing = au.Chain()
            processing.append(image.uri)

            if image.uri.startswith('http://'):
                processing.append(au.HttpUrl)
            elif image.uri.startswith('file://'):
                processing.append(au.LocalFile)

            if image.container == 'gzip':
                processing.append(au.GunzipStream)

            processing.append(image.target_device)
            # For every file system in partitioning scheme we call
            # make_fs utility. That means we do not care whether fs image
            # is available for a particular file system.
            # If image is not available we assume user wants to
            # leave this file system un-touched.
            try:
                processing.process()
            except Exception:
                pass

    def mount_target(self, chroot):
        key = lambda x: len(x.mount.rstrip('/').split('/'))
        for fs in sorted(self.partition_scheme.fss, key=key):
            mount = chroot + fs.mount
            if not os.path.isdir(mount):
                os.makedirs(mount, mode=0755)
            fu.mount_fs(fs.type, fs.device, mount)

    def umount_target(self):
        key = lambda x: len(x.mount.rstrip('/').split('/'))
        for fs in sorted(self.partition_scheme.fss, key=key, reverse=True):
            fu.umount_fs(fs.device)

    def do_bootloader(self):
        chroot = '/tmp/target'
        self.mount_target(chroot)

        grub_version = gu.grub_version_guess(chroot=chroot)
        boot_device = self.partition_scheme.boot_device(grub_version)
        install_devices = [d.name for d in self.partition_scheme.parteds
                           if d.install_bootloader]
        kernel_params = ''

        if grub_version == 1:
            gu.grub1_cfg(kernel_params=kernel_params, chroot=chroot)
            gu.grub1_install(install_devices, boot_device, chroot=chroot)
        else:
            gu.grub2_cfg(kernel_params, chroot=chroot)
            gu.grub2_install(install_devices, chroot=chroot)

        self.umount_target()

    def do_provisioning(self):
        self.do_parsing()
        self.do_partitioning()
        self.do_configdrive()
        self.do_copyimage()
        self.do_bootloader()
