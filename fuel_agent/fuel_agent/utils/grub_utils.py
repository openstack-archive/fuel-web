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
import re
import shutil

from fuel_agent import errors
from fuel_agent.openstack.common import log as logging
from fuel_agent.utils import utils

LOG = logging.getLogger(__name__)


def guess_grub2_conf(chroot=''):
    for filename in ('/boot/grub/grub.cfg', '/boot/grub2/grub.cfg'):
        if os.path.isdir(os.path.dirname(chroot + filename)):
            return filename


def guess_grub2_default(chroot=''):
    for filename in ('/etc/default/grub', '/etc/sysconfig/grub'):
        if os.path.isfile(chroot + filename):
            return filename


def guess_grub2_mkconfig(chroot=''):
    for grub_mkconfig in \
            ('/sbin/grub-mkconfig', '/sbin/grub2-mkconfig',
             '/usr/sbin/grub-mkconfig', '/usr/sbin/grub2-mkconfig'):
        if os.path.isfile(chroot + grub_mkconfig):
            return grub_mkconfig


def guess_grub_version(chroot=''):
    grub_install = guess_grub_install(chroot=chroot)
    LOG.debug('Trying to run %s -v' % grub_install)
    result = utils.execute(chroot + grub_install, '-v')
    version = 1 if result[0].find('0.97') > 0 else 2
    LOG.debug('Looks like grub version is %s' % version)
    return version


def guess_grub(chroot=''):
    for grub in ('/sbin/grub', '/usr/sbin/grub'):
        LOG.debug('Looking for grub: trying %s' % grub)
        if os.path.isfile(chroot + grub):
            LOG.debug('grub found: %s' % grub)
            return grub
    raise errors.GrubUtilsError('grub not found')


def guess_grub_install(chroot=''):
    for grub_install in ('/sbin/grub-install', '/sbin/grub2-install',
                         '/usr/sbin/grub-install', '/usr/sbin/grub2-install'):
        LOG.debug('Looking for grub-install: trying %s' % grub_install)
        if os.path.isfile(chroot + grub_install):
            LOG.debug('grub-install found: %s' % grub_install)
            return grub_install
    raise errors.GrubUtilsError('grub-install not found')


def guess_grub1_datadir(chroot='', arch='x86_64'):
    LOG.debug('Looking for grub data directory')
    for d in os.listdir(chroot + '/usr/share/grub'):
        if arch in d:
            LOG.debug('Looks like grub data directory '
                      'is /usr/share/grub/%s' % d)
            return '/usr/share/grub/' + d


def guess_kernel(chroot=''):
    for filename in sorted(os.listdir(chroot + '/boot'), reverse=True):
        # We assume kernel name is always starts with vmlinuz.
        # We use the newest one.
        if filename.startswith('vmlinuz'):
            return filename
    raise errors.GrubUtilsError('Error while trying to find kernel: not found')


def guess_initrd(chroot=''):
    for filename in sorted(os.listdir(chroot + '/boot'), reverse=True):
        # We assume initrd starts either with initramfs or initrd.
        if filename.startswith('initramfs') or \
                filename.startswith('initrd'):
            return filename
    raise errors.GrubUtilsError('Error while trying to find initrd: not found')


def grub1_install(install_devices, boot_device, chroot=''):
    match = re.search(r'(.+?)(p?)(\d*)$', boot_device)
    # Checking whether boot device is a partition
    # !!! It must be a partition not a whole disk. !!!
    if not match.group(3):
        raise errors.GrubUtilsError(
            'Error while installing legacy grub: '
            'boot device must be a partition')
    boot_disk = match.group(1)
    boot_part = str(int(match.group(3)) - 1)
    grub1_stage1(chroot=chroot)
    for install_device in install_devices:
        grub1_mbr(install_device, boot_disk, boot_part, chroot=chroot)


def grub1_mbr(install_device, boot_disk, boot_part, chroot=''):
    # The device on which we are going to install
    # stage1 needs to be mapped as hd0, otherwise system won't be able to boot.
    batch = 'device (hd0) {0}\n'.format(install_device)
    # That is much easier to use grub-install, but unfortunately
    # it is not able to install bootloader on huge disks.
    # Instead we set drive geometry manually to avoid grub register
    # overlapping. We set it so as to make grub
    # thinking that disk size is equal to 1G.
    # 130 cylinders * (16065 * 512 = 8225280 bytes) = 1G
    # We also assume that boot partition is in the beginning
    # of disk between 0 and 1G.
    batch += 'geometry (hd0) 130 255 63\n'
    if boot_disk != install_device:
        batch += 'device (hd1) {0}\n'.format(boot_disk)
        batch += 'geometry (hd1) 130 255 63\n'
        batch += 'root (hd1,{0})\n'.format(boot_part)
    else:
        batch += 'root (hd0,{0})\n'.format(boot_part)
    batch += 'setup (hd0)\n'
    batch += 'quit\n'

    with open(chroot + '/tmp/grub.batch', 'wb') as f:
        LOG.debug('Grub batch content: \n%s' % batch)
        f.write(batch)

    script = 'cat /tmp/grub.batch | {0} --no-floppy --batch'.format(
        guess_grub(chroot=chroot))
    with open(chroot + '/tmp/grub.sh', 'wb') as f:
        LOG.debug('Grub script content: \n%s' % script)
        f.write(script)

    os.chmod(chroot + '/tmp/grub.sh', 0o755)
    cmd = ['/tmp/grub.sh']
    if chroot:
        cmd[:0] = ['chroot', chroot]
    stdout, stderr = utils.execute(*cmd, run_as_root=True, check_exit_code=[0])
    LOG.debug('Grub script stdout: \n%s' % stdout)
    LOG.debug('Grub script stderr: \n%s' % stderr)


def grub1_stage1(chroot=''):
    LOG.debug('Installing grub stage1 files')
    for f in os.listdir(chroot + '/boot/grub'):
        if f in ('stage1', 'stage2') or 'stage1_5' in f:
            LOG.debug('Removing: %s' % chroot + os.path.join('/boot/grub', f))
            os.remove(chroot + os.path.join('/boot/grub', f))
    grub1_datadir = guess_grub1_datadir(chroot=chroot)
    for f in os.listdir(chroot + grub1_datadir):
        if f in ('stage1', 'stage2') or 'stage1_5' in f:
            LOG.debug('Copying %s from %s to /boot/grub' % (f, grub1_datadir))
            shutil.copy(chroot + os.path.join(grub1_datadir, f),
                        chroot + os.path.join('/boot/grub', f))


def grub1_cfg(kernel=None, initrd=None,
              kernel_params='', chroot=''):

    if not kernel:
        kernel = guess_kernel(chroot=chroot)
    if not initrd:
        initrd = guess_initrd(chroot=chroot)

    config = """
default=0
timeout=5
title Default ({kernel})
    kernel /{kernel} {kernel_params}
    initrd /{initrd}
    """.format(kernel=kernel, initrd=initrd,
               kernel_params=kernel_params)
    with open(chroot + '/boot/grub/grub.conf', 'wb') as f:
        f.write(config)


def grub2_install(install_devices, chroot=''):
    grub_install = guess_grub_install(chroot=chroot)
    for install_device in install_devices:
        cmd = [grub_install, install_device]
        if chroot:
            cmd[:0] = ['chroot', chroot]
        utils.execute(*cmd, run_as_root=True, check_exit_code=[0])


def grub2_cfg(kernel_params='', chroot=''):
    grub_defaults = chroot + guess_grub2_default(chroot=chroot)
    rekerparams = re.compile(r'^.*GRUB_CMDLINE_LINUX=.*')
    retimeout = re.compile(r'^.*GRUB_HIDDEN_TIMEOUT=.*')
    new_content = ''
    with open(grub_defaults) as f:
        for line in f:
            line = rekerparams.sub(
                'GRUB_CMDLINE_LINUX="{kernel_params}"'.
                format(kernel_params=kernel_params), line)
            line = retimeout.sub('GRUB_HIDDEN_TIMEOUT=5', line)
            new_content += line
    with open(grub_defaults, 'wb') as f:
        f.write(new_content)
    cmd = [guess_grub2_mkconfig(chroot), '-o', guess_grub2_conf(chroot)]
    if chroot:
        cmd[:0] = ['chroot', chroot]
    utils.execute(*cmd, run_as_root=True)
