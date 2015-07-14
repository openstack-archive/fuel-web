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
import shutil
import signal
import tempfile
import yaml

from oslo.config import cfg

from fuel_agent import errors
from fuel_agent.openstack.common import log as logging
from fuel_agent.utils import artifact as au
from fuel_agent.utils import build as bu
from fuel_agent.utils import fs as fu
from fuel_agent.utils import grub as gu
from fuel_agent.utils import lvm as lu
from fuel_agent.utils import md as mu
from fuel_agent.utils import partition as pu
from fuel_agent.utils import utils

opts = [
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
    cfg.StrOpt(
        'udev_rules_dir',
        default='/etc/udev/rules.d',
        help='Path where to store actual rules for udev daemon',
    ),
    cfg.StrOpt(
        'udev_rules_lib_dir',
        default='/lib/udev/rules.d',
        help='Path where to store default rules for udev daemon',
    ),
    cfg.StrOpt(
        'udev_rename_substr',
        default='.renamedrule',
        help='Substring to which file extension .rules be renamed',
    ),
    cfg.StrOpt(
        'udev_empty_rule',
        default='empty_rule',
        help='Correct empty rule for udev daemon',
    ),
    cfg.StrOpt(
        'image_build_dir',
        default='/tmp',
        help='Directory where the image is supposed to be built',
    ),
    cfg.StrOpt(
        'image_build_suffix',
        default='.fuel-agent-image',
        help='Suffix which is used while creating temporary files',
    ),
]

cli_opts = [
    cfg.StrOpt(
        'data_driver',
        default='nailgun',
        help='Data driver'
    ),
]

CONF = cfg.CONF
CONF.register_opts(opts)
CONF.register_cli_opts(cli_opts)

LOG = logging.getLogger(__name__)


class Manager(object):
    def __init__(self, data):
        self.driver = utils.get_driver(CONF.data_driver)(data)

    def do_partitioning(self):
        LOG.debug('--- Partitioning disks (do_partitioning) ---')
        # If disks are not wiped out at all, it is likely they contain lvm
        # and md metadata which will prevent re-creating a partition table
        # with 'device is busy' error.
        mu.mdclean_all()
        lu.lvremove_all()
        lu.vgremove_all()
        lu.pvremove_all()

        # Here is udev's rules blacklisting to be done:
        # by adding symlinks to /dev/null in /etc/udev/rules.d for already
        # existent rules in /lib/.
        # 'parted' generates too many udev events in short period of time
        # so we should increase processing speed for those events,
        # otherwise partitioning is doomed.
        empty_rule_path = os.path.join(CONF.udev_rules_dir,
                                       os.path.basename(CONF.udev_empty_rule))
        with open(empty_rule_path, 'w') as f:
            f.write('#\n')
        LOG.debug("Enabling udev's rules blacklisting")
        for rule in os.listdir(CONF.udev_rules_lib_dir):
            dst = os.path.join(CONF.udev_rules_dir, rule)
            if os.path.isdir(dst):
                continue
            if dst.endswith('.rules'):
                # for successful blacklisting already existent file with name
                # from /etc which overlaps with /lib should be renamed prior
                # symlink creation.
                try:
                    if os.path.exists(dst):
                        os.rename(dst, dst[:-len('.rules')] +
                                  CONF.udev_rename_substr)
                except OSError:
                    LOG.debug("Skipping udev rule %s blacklising" % dst)
                else:
                    os.symlink(empty_rule_path, dst)
        utils.execute('udevadm', 'control', '--reload-rules',
                      check_exit_code=[0])

        for parted in self.driver.partition_scheme.parteds:
            for prt in parted.partitions:
                # We wipe out the beginning of every new partition
                # right after creating it. It allows us to avoid possible
                # interactive dialog if some data (metadata or file system)
                # present on this new partition and it also allows udev not
                # hanging trying to parse this data.
                utils.execute('dd', 'if=/dev/zero', 'bs=1M',
                              'seek=%s' % max(prt.begin - 3, 0), 'count=5',
                              'of=%s' % prt.device, check_exit_code=[0])
                # Also wipe out the ending of every new partition.
                # Different versions of md stores metadata in different places.
                # Adding exit code 1 to be accepted as for handling situation
                # when 'no space left on device' occurs.
                utils.execute('dd', 'if=/dev/zero', 'bs=1M',
                              'seek=%s' % max(prt.end - 3, 0), 'count=5',
                              'of=%s' % prt.device, check_exit_code=[0, 1])

        for parted in self.driver.partition_scheme.parteds:
            pu.make_label(parted.name, parted.label)
            for prt in parted.partitions:
                pu.make_partition(prt.device, prt.begin, prt.end, prt.type)
                for flag in prt.flags:
                    pu.set_partition_flag(prt.device, prt.count, flag)
                if prt.guid:
                    pu.set_gpt_type(prt.device, prt.count, prt.guid)
                # If any partition to be created doesn't exist it's an error.
                # Probably it's again 'device or resource busy' issue.
                if not os.path.exists(prt.name):
                    raise errors.PartitionNotFoundError(
                        'Partition %s not found after creation' % prt.name)

        # disable udev's rules blacklisting
        LOG.debug("Disabling udev's rules blacklisting")
        for rule in os.listdir(CONF.udev_rules_dir):
            src = os.path.join(CONF.udev_rules_dir, rule)
            if os.path.isdir(src):
                continue
            if src.endswith('.rules'):
                if os.path.islink(src):
                    try:
                        os.remove(src)
                    except OSError:
                        LOG.debug(
                            "Skipping udev rule %s de-blacklisting" % src)
            elif src.endswith(CONF.udev_rename_substr):
                try:
                    if os.path.exists(src):
                        os.rename(src, src[:-len(CONF.udev_rename_substr)] +
                                  '.rules')
                except OSError:
                    LOG.debug("Skipping udev rule %s de-blacklisting" % src)
        utils.execute('udevadm', 'control', '--reload-rules',
                      check_exit_code=[0])
        # NOTE(agordeev): re-create all the links which were skipped by udev
        # while blacklisted
        # NOTE(agordeev): do subsystem match, otherwise it will stuck
        utils.execute('udevadm', 'trigger', '--subsystem-match=block',
                      check_exit_code=[0])
        utils.execute('udevadm', 'settle', '--quiet', check_exit_code=[0])

        # If one creates partitions with the same boundaries as last time,
        # there might be md and lvm metadata on those partitions. To prevent
        # failing of creating md and lvm devices we need to make sure
        # unused metadata are wiped out.
        mu.mdclean_all()
        lu.lvremove_all()
        lu.vgremove_all()
        lu.pvremove_all()

        if 'centos' in self.driver.configdrive_scheme.profile.lower():
            metadata = '0.90'
        else:
            metadata = 'default'
        # creating meta disks
        for md in self.driver.partition_scheme.mds:
            mu.mdcreate(md.name, md.level, metadata, *md.devices)

        # creating physical volumes
        for pv in self.driver.partition_scheme.pvs:
            lu.pvcreate(pv.name, metadatasize=pv.metadatasize,
                        metadatacopies=pv.metadatacopies)

        # creating volume groups
        for vg in self.driver.partition_scheme.vgs:
            lu.vgcreate(vg.name, *vg.pvnames)

        # creating logical volumes
        for lv in self.driver.partition_scheme.lvs:
            lu.lvcreate(lv.vgname, lv.name, lv.size)

        # making file systems
        for fs in self.driver.partition_scheme.fss:
            found_images = [img for img in self.driver.image_scheme.images
                            if img.target_device == fs.device]
            if not found_images:
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
            tmpl_dir,
            self.driver.configdrive_scheme.template_names('cloud_config'),
            self.driver.configdrive_scheme.template_data(),
            cc_output_path
        )
        utils.render_and_save(
            tmpl_dir,
            self.driver.configdrive_scheme.template_names('boothook'),
            self.driver.configdrive_scheme.template_data(),
            bh_output_path
        )
        utils.render_and_save(
            tmpl_dir,
            self.driver.configdrive_scheme.template_names('meta-data'),
            self.driver.configdrive_scheme.template_data(),
            md_output_path
        )

        utils.execute('write-mime-multipart', '--output=%s' % ud_output_path,
                      '%s:text/cloud-boothook' % bh_output_path,
                      '%s:text/cloud-config' % cc_output_path)
        utils.execute('genisoimage', '-output', CONF.config_drive_path,
                      '-volid', 'cidata', '-joliet', '-rock', ud_output_path,
                      md_output_path)

        configdrive_device = self.driver.partition_scheme.configdrive_device()
        if configdrive_device is None:
            raise errors.WrongPartitionSchemeError(
                'Error while trying to get configdrive device: '
                'configdrive device not found')
        size = os.path.getsize(CONF.config_drive_path)
        md5 = utils.calculate_md5(CONF.config_drive_path, size)
        self.driver.image_scheme.add_image(
            uri='file://%s' % CONF.config_drive_path,
            target_device=configdrive_device,
            format='iso9660',
            container='raw',
            size=size,
            md5=md5,
        )

    def do_copyimage(self):
        LOG.debug('--- Copying images (do_copyimage) ---')
        for image in self.driver.image_scheme.images:
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

            if image.size and image.md5:
                LOG.debug('Trying to compare image checksum')
                actual_md5 = utils.calculate_md5(image.target_device,
                                                 image.size)
                if actual_md5 == image.md5:
                    LOG.debug('Checksum matches successfully: md5=%s' %
                              actual_md5)
                else:
                    raise errors.ImageChecksumMismatchError(
                        'Actual checksum %s mismatches with expected %s for '
                        'file %s' % (actual_md5, image.md5,
                                     image.target_device))
            else:
                LOG.debug('Skipping image checksum comparing. '
                          'Ether size or hash have been missed')

            LOG.debug('Extending image file systems')
            if image.format in ('ext2', 'ext3', 'ext4', 'xfs'):
                LOG.debug('Extending %s %s' %
                          (image.format, image.target_device))
                fu.extend_fs(image.format, image.target_device)

    # TODO(kozhukalov): write tests
    def mount_target(self, chroot, treat_mtab=True, pseudo=True):
        """Mount a set of file systems into a chroot

        :param chroot: Directory where to mount file systems
        :param treat_mtab: If mtab needs to be actualized (Default: True)
        :param pseudo: If pseudo file systems
        need to be mounted (Default: True)
        """
        LOG.debug('Mounting target file systems: %s', chroot)
        # Here we are going to mount all file systems in partition scheme.
        for fs in self.driver.partition_scheme.fs_sorted_by_depth():
            if fs.mount == 'swap':
                continue
            mount = chroot + fs.mount
            utils.makedirs_if_not_exists(mount)
            fu.mount_fs(fs.type, str(fs.device), mount)

        if pseudo:
            for path in ('/sys', '/dev', '/proc'):
                utils.makedirs_if_not_exists(chroot + path)
                fu.mount_bind(chroot, path)

        if treat_mtab:
            mtab = utils.execute(
                'chroot', chroot, 'grep', '-v', 'rootfs', '/proc/mounts')[0]
            mtab_path = chroot + '/etc/mtab'
            if os.path.islink(mtab_path):
                os.remove(mtab_path)
            with open(mtab_path, 'wb') as f:
                f.write(mtab)

    # TODO(kozhukalov): write tests for this method
    def umount_target(self, chroot, pseudo=True, try_lazy_umount=True):
        LOG.debug('Umounting target file systems: %s', chroot)
        if pseudo:
            for path in ('/proc', '/dev', '/sys'):
                fu.umount_fs(chroot + path, try_lazy_umount=try_lazy_umount)
        for fs in self.driver.partition_scheme.fs_sorted_by_depth(
                reverse=True):
            if fs.mount == 'swap':
                continue
            fu.umount_fs(chroot + fs.mount, try_lazy_umount=try_lazy_umount)

    # TODO(kozhukalov): write tests for this method
    # https://bugs.launchpad.net/fuel/+bug/1449609
    def do_bootloader(self):
        LOG.debug('--- Installing bootloader (do_bootloader) ---')
        chroot = '/tmp/target'
        self.mount_target(chroot)

        mount2uuid = {}
        for fs in self.driver.partition_scheme.fss:
            mount2uuid[fs.mount] = utils.execute(
                'blkid', '-o', 'value', '-s', 'UUID', fs.device,
                check_exit_code=[0])[0].strip()

        grub = self.driver.grub

        grub.version = gu.guess_grub_version(chroot=chroot)
        boot_device = self.driver.partition_scheme.boot_device(grub.version)
        install_devices = [d.name for d in self.driver.partition_scheme.parteds
                           if d.install_bootloader]

        grub.append_kernel_params('root=UUID=%s ' % mount2uuid['/'])

        kernel = grub.kernel_name or \
            gu.guess_kernel(chroot=chroot, regexp=grub.kernel_regexp)
        initrd = grub.initrd_name or \
            gu.guess_initrd(chroot=chroot, regexp=grub.initrd_regexp)

        if grub.version == 1:
            gu.grub1_cfg(kernel=kernel, initrd=initrd,
                         kernel_params=grub.kernel_params, chroot=chroot)
            gu.grub1_install(install_devices, boot_device, chroot=chroot)
        else:
            # TODO(kozhukalov): implement which kernel to use by default
            # Currently only grub1_cfg accepts kernel and initrd parameters.
            gu.grub2_cfg(kernel_params=grub.kernel_params, chroot=chroot)
            gu.grub2_install(install_devices, chroot=chroot)

        # FIXME(agordeev) There's no convenient way to perfrom NIC remapping in
        #  Ubuntu, so injecting files prior the first boot should work
        with open(chroot + '/etc/udev/rules.d/70-persistent-net.rules',
                  'w') as f:
            f.write('# Generated by fuel-agent during provisioning: BEGIN\n')
            # pattern is aa:bb:cc:dd:ee:ff_eth0,aa:bb:cc:dd:ee:ff_eth1
            for mapping in self.driver.configdrive_scheme.\
                    common.udevrules.split(','):
                mac_addr, nic_name = mapping.split('_')
                f.write('SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", '
                        'ATTR{address}=="%s", ATTR{type}=="1", KERNEL=="eth*",'
                        ' NAME="%s"\n' % (mac_addr, nic_name))
            f.write('# Generated by fuel-agent during provisioning: END\n')
        # FIXME(agordeev): Disable net-generator that will add new etries to
        # 70-persistent-net.rules
        with open(chroot +
                  '/etc/udev/rules.d/75-persistent-net-generator.rules',
                  'w') as f:
            f.write('# Generated by fuel-agent during provisioning:\n'
                    '# DO NOT DELETE. It is needed to disable net-generator\n')

        # FIXME(kozhukalov): Prevent nailgun-agent from doing anything.
        # This ugly hack is to be used together with the command removing
        # this lock file not earlier than /etc/rc.local
        # The reason for this hack to appear is to prevent nailgun-agent from
        # changing mcollective config at the same time when cloud-init
        # does the same. Otherwise, we can end up with corrupted mcollective
        # config. For details see https://bugs.launchpad.net/fuel/+bug/1449186
        LOG.debug('Preventing nailgun-agent from doing '
                  'anything until it is unlocked')
        utils.makedirs_if_not_exists(os.path.join(chroot, 'etc/nailgun-agent'))
        with open(os.path.join(chroot, 'etc/nailgun-agent/nodiscover'), 'w'):
            pass

        with open(chroot + '/etc/fstab', 'wb') as f:
            for fs in self.driver.partition_scheme.fss:
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
        self.do_partitioning()
        self.do_configdrive()
        self.do_copyimage()
        self.do_bootloader()
        LOG.debug('--- Provisioning END (do_provisioning) ---')

    # TODO(kozhukalov): Split this huge method
    # into a set of smaller ones
    # https://bugs.launchpad.net/fuel/+bug/1444090
    def do_build_image(self):
        """Building OS images

        Includes the following steps
        1) create temporary sparse files for all images (truncate)
        2) attach temporary files to loop devices (losetup)
        3) create file systems on these loop devices
        4) create temporary chroot directory
        5) mount loop devices into chroot directory
        6) install operating system (debootstrap and apt-get)
        7) configure OS (clean sources.list and preferences, etc.)
        8) umount loop devices
        9) resize file systems on loop devices
        10) shrink temporary sparse files (images)
        11) containerize (gzip) temporary sparse files
        12) move temporary gzipped files to their final location
        """
        LOG.info('--- Building image (do_build_image) ---')
        # TODO(kozhukalov): Implement metadata
        # as a pluggable data driver to avoid any fixed format.
        metadata = {}

        # TODO(kozhukalov): implement this using image metadata
        # we need to compare list of packages and repos
        LOG.info('*** Checking if image exists ***')
        if all([os.path.exists(img.uri.split('file://', 1)[1])
                for img in self.driver.image_scheme.images]):
            LOG.debug('All necessary images are available. '
                      'Nothing needs to be done.')
            return
        LOG.debug('At least one of the necessary images is unavailable. '
                  'Starting build process.')
        try:
            LOG.debug('Creating temporary chroot directory')
            chroot = tempfile.mkdtemp(
                dir=CONF.image_build_dir, suffix=CONF.image_build_suffix)
            LOG.debug('Temporary chroot: %s', chroot)

            proc_path = os.path.join(chroot, 'proc')

            LOG.info('*** Preparing image space ***')
            for image in self.driver.image_scheme.images:
                LOG.debug('Creating temporary sparsed file for the '
                          'image: %s', image.uri)
                img_tmp_file = bu.create_sparse_tmp_file(
                    dir=CONF.image_build_dir, suffix=CONF.image_build_suffix)
                LOG.debug('Temporary file: %s', img_tmp_file)

                # we need to remember those files
                # to be able to shrink them and move in the end
                image.img_tmp_file = img_tmp_file

                LOG.debug('Looking for a free loop device')
                image.target_device.name = bu.get_free_loop_device()

                LOG.debug('Attaching temporary image file to free loop device')
                bu.attach_file_to_loop(img_tmp_file, str(image.target_device))

                # find fs with the same loop device object
                # as image.target_device
                fs = self.driver.partition_scheme.fs_by_device(
                    image.target_device)

                LOG.debug('Creating file system on the image')
                fu.make_fs(
                    fs_type=fs.type,
                    fs_options=fs.options,
                    fs_label=fs.label,
                    dev=str(fs.device))
                if fs.type == 'ext4':
                    LOG.debug('Trying to disable journaling for ext4 '
                              'in order to speed up the build')
                    utils.execute('tune2fs', '-O', '^has_journal',
                                  str(fs.device))

            # mounting all images into chroot tree
            self.mount_target(chroot, treat_mtab=False, pseudo=False)

            LOG.info('*** Shipping image content ***')
            LOG.debug('Installing operating system into image')
            # FIXME(kozhukalov): !!! we need this part to be OS agnostic

            # DEBOOTSTRAP
            # we use first repo as the main mirror
            uri = self.driver.operating_system.repos[0].uri
            suite = self.driver.operating_system.repos[0].suite

            LOG.debug('Preventing services from being get started')
            bu.suppress_services_start(chroot)
            LOG.debug('Installing base operating system using debootstrap')
            bu.run_debootstrap(uri=uri, suite=suite, chroot=chroot)

            # APT-GET
            LOG.debug('Configuring apt inside chroot')
            LOG.debug('Setting environment variables')
            bu.set_apt_get_env()
            LOG.debug('Allowing unauthenticated repos')
            bu.pre_apt_get(chroot)

            for repo in self.driver.operating_system.repos:
                LOG.debug('Adding repository source: name={name}, uri={uri},'
                          'suite={suite}, section={section}'.format(
                              name=repo.name, uri=repo.uri,
                              suite=repo.suite, section=repo.section))
                bu.add_apt_source(
                    name=repo.name,
                    uri=repo.uri,
                    suite=repo.suite,
                    section=repo.section,
                    chroot=chroot)
                LOG.debug('Adding repository preference: '
                          'name={name}, priority={priority}'.format(
                              name=repo.name, priority=repo.priority))
                if repo.priority is not None:
                    bu.add_apt_preference(
                        name=repo.name,
                        priority=repo.priority,
                        suite=repo.suite,
                        section=repo.section,
                        chroot=chroot,
                        uri=repo.uri)

                metadata.setdefault('repos', []).append({
                    'type': 'deb',
                    'name': repo.name,
                    'uri': repo.uri,
                    'suite': repo.suite,
                    'section': repo.section,
                    'priority': repo.priority,
                    'meta': repo.meta})

            LOG.debug('Preventing services from being get started')
            bu.suppress_services_start(chroot)

            packages = self.driver.operating_system.packages
            metadata['packages'] = packages

            # we need /proc to be mounted for apt-get success
            utils.makedirs_if_not_exists(proc_path)
            fu.mount_bind(chroot, '/proc')

            LOG.debug('Installing packages using apt-get: %s',
                      ' '.join(packages))
            bu.run_apt_get(chroot, packages=packages)

            LOG.debug('Post-install OS configuration')
            bu.do_post_inst(chroot)

            LOG.debug('Making sure there are no running processes '
                      'inside chroot before trying to umount chroot')
            if not bu.stop_chrooted_processes(chroot, signal=signal.SIGTERM):
                if not bu.stop_chrooted_processes(
                        chroot, signal=signal.SIGKILL):
                    raise errors.UnexpectedProcessError(
                        'Stopping chrooted processes failed. '
                        'There are some processes running in chroot %s',
                        chroot)

            LOG.info('*** Finalizing image space ***')
            fu.umount_fs(proc_path)
            # umounting all loop devices
            self.umount_target(chroot, pseudo=False, try_lazy_umount=False)

            for image in self.driver.image_scheme.images:
                # find fs with the same loop device object
                # as image.target_device
                fs = self.driver.partition_scheme.fs_by_device(
                    image.target_device)

                if fs.type == 'ext4':
                    LOG.debug('Trying to re-enable journaling for ext4')
                    utils.execute('tune2fs', '-O', 'has_journal',
                                  str(fs.device))

                LOG.debug('Deattaching loop device from file: %s',
                          image.img_tmp_file)
                bu.deattach_loop(str(image.target_device))
                LOG.debug('Shrinking temporary image file: %s',
                          image.img_tmp_file)
                bu.shrink_sparse_file(image.img_tmp_file)

                raw_size = os.path.getsize(image.img_tmp_file)
                raw_md5 = utils.calculate_md5(image.img_tmp_file, raw_size)

                LOG.debug('Containerizing temporary image file: %s',
                          image.img_tmp_file)
                img_tmp_containerized = bu.containerize(
                    image.img_tmp_file, image.container)
                img_containerized = image.uri.split('file://', 1)[1]

                # NOTE(kozhukalov): implement abstract publisher
                LOG.debug('Moving image file to the final location: %s',
                          img_containerized)
                shutil.move(img_tmp_containerized, img_containerized)

                container_size = os.path.getsize(img_containerized)
                container_md5 = utils.calculate_md5(
                    img_containerized, container_size)
                metadata.setdefault('images', []).append({
                    'raw_md5': raw_md5,
                    'raw_size': raw_size,
                    'raw_name': None,
                    'container_name': os.path.basename(img_containerized),
                    'container_md5': container_md5,
                    'container_size': container_size,
                    'container': image.container,
                    'format': image.format})

            # NOTE(kozhukalov): implement abstract publisher
            LOG.debug('Image metadata: %s', metadata)
            with open(self.driver.metadata_uri.split('file://', 1)[1],
                      'w') as f:
                yaml.safe_dump(metadata, stream=f)
            LOG.info('--- Building image END (do_build_image) ---')
        except Exception as exc:
            LOG.error('Failed to build image: %s', exc)
            raise
        finally:
            LOG.debug('Finally: stopping processes inside chroot: %s', chroot)

            if not bu.stop_chrooted_processes(chroot, signal=signal.SIGTERM):
                bu.stop_chrooted_processes(chroot, signal=signal.SIGKILL)
            LOG.debug('Finally: umounting procfs %s', proc_path)
            fu.umount_fs(proc_path)
            LOG.debug('Finally: umounting chroot tree %s', chroot)
            self.umount_target(chroot, pseudo=False, try_lazy_umount=False)
            for image in self.driver.image_scheme.images:
                LOG.debug('Finally: detaching loop device: %s',
                          str(image.target_device))
                try:
                    bu.deattach_loop(str(image.target_device))
                except errors.ProcessExecutionError as e:
                    LOG.warning('Error occured while trying to detach '
                                'loop device %s. Error message: %s',
                                str(image.target_device), e)

                LOG.debug('Finally: removing temporary file: %s',
                          image.img_tmp_file)
                try:
                    os.unlink(image.img_tmp_file)
                except OSError:
                    LOG.debug('Finally: file %s seems does not exist '
                              'or can not be removed', image.img_tmp_file)
            LOG.debug('Finally: removing chroot directory: %s', chroot)
            try:
                os.rmdir(chroot)
            except OSError:
                LOG.debug('Finally: directory %s seems does not exist '
                          'or can not be removed', chroot)
