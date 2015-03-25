#    Copyright 2015 Mirantis, Inc.
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

import os
import stat
import tempfile

from oslo.config import cfg

from fuel_agent import errors
from fuel_agent.openstack.common import log as logging
from fuel_agent.utils import hardware_utils as hu
from fuel_agent.utils import utils

LOG = logging.getLogger(__name__)

bu_opts = [
    cfg.StrOpt(
        'sparse_prefix',
        default="fuel-image-sparse-",
        help='Prefix to be used for sparse file names'
    ),
    cfg.StrOpt(
        'tmp_dir_sparse',
        default=tempfile.mkdtemp(),
        help='Temporary directory to be used for sparse files'
    ),
    cfg.IntOpt(
        'max_loop_count',
        default=255,
        help='Maximum allowed loop devices count to use'
    ),
    cfg.IntOpt(
        'sparse_file_size',
        default=2048,
        help='Size of sparse file in MiBs'
    ),
    cfg.IntOpt(
        'loop_dev_major',
        default=7,
        help='System-wide major number for loop device'
    ),
]

CONF = cfg.CONF
CONF.register_opts(bu_opts)


def run_deboostrap(arch, release, chroot, mirror_url, prefetch=False):
    #TODO(agordeev): do retry!
    cmds = ['debootstrap', '--verbose', '--no-check-gpg', '--arch=%s' % arch,
            release, chroot, mirror_url]
    if prefetch:
        cmds.insert(2, '--download-only')
    utils.execute(*cmds)


def set_apt_get_env():
    os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
    os.environ['DEBCONF_NONINTERACTIVE_SEEN'] = 'true'
    os.environ['LC_ALL'] = os.environ['LANG'] = os.environ['LANGUAGE'] = 'C'


def run_apt_get(chroot, packages, prefetch=False):
    #TODO(agordeev): do retry!
    cmds = ['chroot', chroot, 'apt-get', '-y', 'install', ' '.join(packages)]
    if prefetch:
        cmds.insert(4, '--download-only')
    utils.execute(*cmds)


def suppress_services_start(chroot):
    path = os.path.join(chroot, 'usr/sbin')
    if not os.path.exists(path):
        os.makedirs(os.path.join(chroot, 'usr/bin'))
    with open(os.path.join(path, 'policy-rc.d'), 'w') as f:
        f.write('#!/bin/sh\n'
                '# prevent any service from being started\n'
                'exit 101\n')
        os.fchmod(f, 0o755)


def do_post_inst(chroot):
    utils.execute('sed', '-i', 's%root:[\*,\!]%root:$6$IInX3Cqo$5xytL1VZbZTusO'
                  'ewFnG6couuF0Ia61yS3rbC6P5YbZP2TYclwHqMq9e3Tg8rvQxhxSlBXP1DZ'
                  'hdUamxdOBXK0.%', os.path.join(chroot, 'etc/shadow'))
    files = ['usr/sbin/policy-rc.d', 'etc/apt/sources.list',
             'etc/apt/preferences', 'etc/apt/apt.conf.d/02mira-unauth']
    for f in files:
        path = os.path.join(chroot, f)
        if os.path.exist(path):
            os.remove(path)


def signal_chrooted_processes(chroot, signal):
    for p in utils.execute('fuser', '-v', chroot)[0].split():
        try:
            pid = int(p)
            proc_root = os.readlink('/proc/%s/root' % p)
            if proc_root == chroot:
                LOG.debug('Sending %s to chrooted process %s' % (signal, pid))
                os.kill(pid, signal)
        except (OSError, ValueError):
            LOG.warning('Skipping non pid %s from fuser output' % p)


def get_free_loop(loop_count=8):
    loop_dev = ''
    while not loop_dev:
        for minor in range(0, loop_count):
            cur_loop = "/dev/loop%s" % minor
            if not os.path.exists(cur_loop):
                os.mknod(cur_loop, 0o660 | stat.S_IFBLK,
                         os.makedev(CONF.loop_dev_major, minor))
        if loop_count >= CONF.max_loop_count:
            raise errors.TooManyLoopDevices(
                'Too many loop devices are used: %s' % loop_count)
        loop_count *= 2
        loop_dev = utils.execute('losetup', '--find')[0].split()[0]
    return loop_dev


def create_sparsed_tmp_file():
    tf = tempfile.NamedTemporaryFile(prefix=CONF.sparse_prefix,
                                     dir=CONF.tmp_dir_sparse,
                                     delete=False)
    utils.execute('truncate', '-s', '%sM' % CONF.sparse_file_size, tf.name)
    return tf.name


def attach_file_to_loop(loop, filename):
    utils.execute('losetup', loop, filename)


def deattach_loop(loop):
    utils.execute('losetup', '-d', loop)


def shrink_sparse_file(filename):
    utils.execute('e2fsck', '-y', '-f', filename)
    utils.execute('resize2fs', '-F', '-M', filename)
    data = hu.parse_simple_kv('dumpe2fs', filename)
    block_count = int(data['block count'])
    block_size = int(data['block size'])
    with open(filename, 'rwb+') as f:
        f.truncate(block_count * block_size)
