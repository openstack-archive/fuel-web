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
import time

from oslo.config import cfg

from fuel_agent import errors
from fuel_agent.openstack.common import log as logging
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

LOG = logging.getLogger(__name__)


class Manager(object):
    def __init__(self, data):
        self.driver = utils.get_driver(CONF.data_driver)(data)
        self.partition_scheme = None
        self.configdrive_scheme = None
        self.image_scheme = None

    def do_parsing(self):
        LOG.debug('--- Parsing data (do_parsing) ---')
        self.partition_scheme = self.driver.partition_scheme()
        self.configdrive_scheme = self.driver.configdrive_scheme()
        self.image_scheme = self.driver.image_scheme(self.partition_scheme)

    def do_partitioning(self):
        LOG.debug('--- Partitioning disks (do_partitioning) ---')
        # If disks are not wiped out at all, it is likely they contain lvm
        # and md metadata which will prevent re-creating a partition table
        # with 'device is busy' error.
        mu.mdclean_all()
        lu.lvremove_all()
        lu.vgremove_all()
        lu.pvremove_all()

        for parted in self.partition_scheme.parteds:
            pu.make_label(parted.name, parted.label)
            for prt in parted.partitions:
                pu.make_partition(prt.device, prt.begin, prt.end, prt.type)
                # We wipe out the beginning of every new partition
                # right after creating it. It allows us to avoid possible
                # interactive dialog if some data (metadata or file system)
                # present on this new partition.
                timestamp = time.time()
                while 1:
                    if time.time() > timestamp + 30:
                        raise errors.PartitionNotFoundError(
                            'Error while wiping data on partition %s.'
                            'Partition not found' % prt.name)
                    try:
                        utils.execute('test', '-e', prt.name,
                                      check_exit_code=[0])
                    except errors.ProcessExecutionError:
                        time.sleep(1)
                        continue
                    else:
                        utils.execute('dd', 'if=/dev/zero', 'bs=1M', 'count=1',
                                      'of=%s' % prt.name, check_exit_code=[0])
                        break

                for flag in prt.flags:
                    pu.set_partition_flag(prt.device, prt.count, flag)
                if prt.guid:
                    pu.set_gpt_type(prt.device, prt.count, prt.guid)

        # If one creates partitions with the same boundaries as last time,
        # there might be md and lvm metadata on those partitions. To prevent
        # failing of creating md and lvm devices we need to make sure
        # unused metadata are wiped out.
        mu.mdclean_all()
        lu.lvremove_all()
        lu.vgremove_all()
        lu.pvremove_all()

        # creating meta disks
        for md in self.partition_scheme.mds:
            mu.mdcreate(md.name, md.level, *md.devices)

        # creating physical volumes
        for pv in self.partition_scheme.pvs:
            lu.pvcreate(pv.name, metadatasize=pv.metadatasize,
                        metadatacopies=pv.metadatacopies)

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
        LOG.debug('--- Creating configdrive (do_configdrive) ---')
        cc_output_path = os.path.join(CONF.tmp_path, 'cloud_config.txt')
        bh_output_path = os.path.join(CONF.tmp_path, 'boothook.txt')
        # NOTE:file should be strictly named as 'user-data'
        #      the same is for meta-data as well
        ud_output_path = os.path.join(CONF.tmp_path, 'user-data')
        md_output_path = os.path.join(CONF.tmp_path, 'meta-data')

        tmpl_dir = CONF.nc_template_path
        utils.render_and_save(
            tmpl_dir, self.configdrive_scheme.template_names('cloud_config'),
            self.configdrive_scheme.template_data(), cc_output_path
        )
        utils.render_and_save(
            tmpl_dir, self.configdrive_scheme.template_names('boothook'),
            self.configdrive_scheme.template_data(), bh_output_path
        )
        utils.render_and_save(
            tmpl_dir, self.configdrive_scheme.template_names('meta-data'),
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
            format='iso9660',
            container='raw'
        )

    def do_copyimage(self):
        LOG.debug('--- Copying images (do_copyimage) ---')
        for image in self.image_scheme.images:
            LOG.debug('Processing image: %s' % image.uri)
            processing = au.Chain()

            LOG.debug('Appending uri processor: %s' % image.uri)
            processing.append(image.uri)

            if image.uri.startswith('http://'):
                LOG.debug('Appending HTTP processor')
                processing.append(au.HttpUrl)
            elif image.uri.startswith('file://'):
                LOG.debug('Appending FILE processor')
                processing.append(au.LocalFile)

            if image.container == 'gzip':
                LOG.debug('Appending GZIP processor')
                processing.append(au.GunzipStream)

            LOG.debug('Appending TARGET processor: %s' % image.target_device)
            processing.append(image.target_device)

            LOG.debug('Launching image processing chain')
            processing.process()

            LOG.debug('Extending image file systems')
            if image.format in ('ext2', 'ext3', 'ext4', 'xfs'):
                LOG.debug('Extending %s %s' %
                          (image.format, image.target_device))
                fu.extend_fs(image.format, image.target_device)

    def mount_target(self, chroot):
        LOG.debug('Mounting target file systems')
        # Here we are going to mount all file systems in partition scheme.
        # Shorter paths earlier. We sort all mount points by their depth.
        # ['/', '/boot', '/var', '/var/lib/mysql']
        key = lambda x: len(x.mount.rstrip('/').split('/'))
        for fs in sorted(self.partition_scheme.fss, key=key):
            if fs.mount == 'swap':
                continue
            mount = chroot + fs.mount
            if not os.path.isdir(mount):
                os.makedirs(mount, mode=0o755)
            fu.mount_fs(fs.type, fs.device, mount)
        fu.mount_bind(chroot, '/sys')
        fu.mount_bind(chroot, '/dev')
        fu.mount_bind(chroot, '/proc')
        mtab = utils.execute(
            'chroot', chroot, 'grep', '-v', 'rootfs', '/proc/mounts')[0]
        mtab_path = chroot + '/etc/mtab'
        if os.path.islink(mtab_path):
            os.remove(mtab_path)
        with open(mtab_path, 'wb') as f:
            f.write(mtab)

    def umount_target(self, chroot):
        LOG.debug('Umounting target file systems')
        fu.umount_fs(chroot + '/proc')
        fu.umount_fs(chroot + '/dev')
        fu.umount_fs(chroot + '/sys')
        key = lambda x: len(x.mount.rstrip('/').split('/'))
        for fs in sorted(self.partition_scheme.fss, key=key, reverse=True):
            if fs.mount == 'swap':
                continue
            fu.umount_fs(fs.device)

    def do_bootloader(self):
        LOG.debug('--- Installing bootloader (do_bootloader) ---')
        chroot = '/tmp/target'
        self.mount_target(chroot)

        mount2uuid = {}
        for fs in self.partition_scheme.fss:
            mount2uuid[fs.mount] = utils.execute(
                'blkid', '-o', 'value', '-s', 'UUID', fs.device,
                check_exit_code=[0])[0].strip()

        grub_version = gu.guess_grub_version(chroot=chroot)
        boot_device = self.partition_scheme.boot_device(grub_version)
        install_devices = [d.name for d in self.partition_scheme.parteds
                           if d.install_bootloader]

        kernel_params = self.partition_scheme.kernel_params
        kernel_params += ' root=UUID=%s ' % mount2uuid['/']

        if grub_version == 1:
            gu.grub1_cfg(kernel_params=kernel_params, chroot=chroot)
            gu.grub1_install(install_devices, boot_device, chroot=chroot)
        else:
            gu.grub2_cfg(kernel_params=kernel_params, chroot=chroot)
            gu.grub2_install(install_devices, chroot=chroot)

        with open(chroot + '/etc/fstab', 'wb') as f:
            for fs in self.partition_scheme.fss:
                # TODO(kozhukalov): Think of improving the logic so as to
                # insert a meaningful fsck order value which is last zero
                # at fstab line. Currently we set it into 0 which means
                # a corresponding file system will never be checked. We assume
                # puppet or other configuration tool will care of it.
                f.write('UUID=%s %s %s defaults 0 0\n' %
                        (mount2uuid[fs.mount], fs.mount, fs.type))

        self.umount_target(chroot)

    def do_reboot(self):
        LOG.debug('--- Rebooting node (do_reboot) ---')
        utils.execute('reboot')

    def do_provisioning(self):
        LOG.debug('--- Provisioning (do_provisioning) ---')
        self.do_parsing()
        self.do_partitioning()
        self.do_configdrive()
        self.do_copyimage()
        self.do_bootloader()
