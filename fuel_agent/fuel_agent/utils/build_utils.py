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

import gzip
import os
import shutil
import stat
import tempfile

from oslo.config import cfg

from fuel_agent import errors
from fuel_agent.openstack.common import log as logging
from fuel_agent.utils import hardware_utils as hu
from fuel_agent.utils import utils

LOG = logging.getLogger(__name__)

bu_opts = [
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
    cfg.StrOpt(
        'allow_unsigned_file',
        default='allow_unsigned_packages',
        help='File where to store apt setting for unsigned packages'
    ),
]

CONF = cfg.CONF
CONF.register_opts(bu_opts)
DEFAULT_APT_PATH = {
    'sources_file': 'etc/apt/sources.list',
    'sources_dir': 'etc/apt/sources.list.d',
    'preferences_file': 'etc/apt/preferences',
    'preferences_dir': 'etc/apt/preferences.d',
    'conf_dir': 'etc/apt/apt.conf.d',
}
#NOTE(agordeev): hardcoded to r00tme
ROOT_PASSWORD = '$6$IInX3Cqo$5xytL1VZbZTusOewFnG6couuF0Ia61yS3rbC6P5YbZP2TYcl'\
                'wHqMq9e3Tg8rvQxhxSlBXP1DZhdUamxdOBXK0.'


#NOTE(agordeev): debootstrap build initial base system which is capable to
# run apt-get. debootstrap is well known for its glithcy resolving of package
# dependecies, so the rest of packages will be installed later by run_apt_get
def run_debootstrap(uri, suite, chroot, arch='amd64', eatmydata=False):
    #TODO(agordeev): do retry!
    cmds = ['debootstrap', '--verbose', '--no-check-gpg', '--arch=%s' % arch,
            suite, chroot, uri]
    if eatmydata:
        cmds.insert(4, '--include=eatmydata')
    stdout, stderr = utils.execute(*cmds)
    LOG.debug('Running deboostrap completed.\nstdout: %s\nstderr: %s', stdout,
              stderr)


def set_apt_get_env():
    #NOTE(agordeev): disable any confirmations/questions from apt-get side
    os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
    os.environ['DEBCONF_NONINTERACTIVE_SEEN'] = 'true'
    os.environ['LC_ALL'] = os.environ['LANG'] = os.environ['LANGUAGE'] = 'C'


#NOTE(agordeev): unlike debootstrap, apt-get has a perfect package dependecies
# resolver under the hood
def run_apt_get(chroot, packages, eatmydata=False):
    #TODO(agordeev): do retry!
    cmds = ['chroot', chroot, 'apt-get', '-y', 'update']
    stdout, stderr = utils.execute(*cmds)
    LOG.debug('Running apt-get update completed.\nstdout: %s\nstderr: %s',
              stdout, stderr)
    cmds = ['chroot', chroot, 'apt-get', '-y', 'install', ' '.join(packages)]
    # eatmydata could be used to totally ignore the storm of sync() calls from
    # dpkg/apt-get tools. It's dangerous, but could decrease package install
    # time in X times.
    if eatmydata:
        cmds.insert(2, 'eatmydata')
    stdout, stderr = utils.execute(*cmds)
    LOG.debug('Running apt-get install completed.\nstdout: %s\nstderr: %s',
              stdout, stderr)


#NOTE(agordeev): prevent start of any service such as udev/ssh/etc in chrooted
# environment while image is being built
def suppress_services_start(chroot):
    path = os.path.join(chroot, 'usr/sbin')
    if not os.path.exists(path):
        os.makedirs(path)
    with open(os.path.join(path, 'policy-rc.d'), 'w') as f:
        f.write('#!/bin/sh\n'
                '# prevent any service from being started\n'
                'exit 101\n')
        os.fchmod(f.fileno(), 0o755)


def remove_dirs(chroot, dirs):
    for d in dirs:
        path = os.path.join(chroot, d)
        if os.path.isdir(path):
            shutil.rmtree(path)
            os.makedirs(path)
            LOG.debug('Removed dir: %s', path)


def remove_files(chroot, files):
    for f in files:
        path = os.path.join(chroot, f)
        if os.path.exists(path):
            os.remove(path)
            LOG.debug('Removed file: %s', path)


#NOTE(agordeev): clean apt settings such as package sources and repo pinning
def clean_apt(chroot):
    files = [DEFAULT_APT_PATH['sources_file'],
             DEFAULT_APT_PATH['preferences_file'],
             os.path.join(DEFAULT_APT_PATH['conf_dir'],
                          CONF.allow_unsigned_file)]
    remove_files(chroot, files)
    dirs = [DEFAULT_APT_PATH['preferences_dir'],
            DEFAULT_APT_PATH['sources_dir']]
    remove_dirs(chroot, dirs)


def do_post_inst(chroot):
    #NOTE(agordeev): set up password for root
    utils.execute('sed', '-i',
                  's%root:[\*,\!]%root:' + ROOT_PASSWORD + '%',
                  os.path.join(chroot, 'etc/shadow'))
    #NOTE(agordeev): remove custom policy-rc.d which is needed to disable
    # execution of post/pre-install package hooks and start of services
    remove_files(chroot, ['usr/sbin/policy-rc.d'])
    clean_apt(chroot)


#NOTE(agordeev): signal to all processes, which are running inside of chroot
def signal_chrooted_processes(chroot, signal):
    for p in utils.execute('fuser', '-v', chroot,
                           check_exit_code=False)[0].split():
        try:
            pid = int(p)
            proc_root = os.readlink('/proc/%s/root' % p)
            if proc_root == chroot:
                LOG.debug('Sending %s to chrooted process %s' % (signal, pid))
                os.kill(pid, signal)
        except (OSError, ValueError):
            LOG.warning('Skipping non pid %s from fuser output' % p)


#NOTE(agordeev): it should return the name of free loop device or raise an
# exception. Unfortunately, free loop device couldn't be reversed for the later
# usage, so we must start to use it as fast as we can.
# If there's no free loop it will try to create new one and ask a system for
# free loop again.
def get_free_loop():
    loop_dev = None
    for minor in range(0, CONF.max_loop_count):
        cur_loop = "/dev/loop%s" % minor
        if not os.path.exists(cur_loop):
            os.mknod(cur_loop, 0o660 | stat.S_IFBLK,
                     os.makedev(CONF.loop_dev_major, minor))
        try:
            loop_dev = utils.execute('losetup', '--find')[0].split()[0]
        except (IndexError, errors.ProcessExecutionError):
            LOG.debug("Couldn't find free loop device, trying again")
        else:
            return loop_dev
    raise errors.NoFreeLoopDevices('Free loop device not found')


#NOTE(agordeev): create file which consumes disk space more efficiently when
# the file itself is mostly empty.
def create_sparse_tmp_file(dir, suffix):
    tf = tempfile.NamedTemporaryFile(dir=dir, suffix=suffix, delete=False)
    utils.execute('truncate', '-s', '%sM' % CONF.sparse_file_size, tf.name)
    return tf.name


def attach_file_to_loop(loop, filename):
    utils.execute('losetup', loop, filename)


def deattach_loop(loop):
    utils.execute('losetup', '-d', loop)


#NOTE(agordeev): truncate file to its size of actual data
def shrink_sparse_file(filename):
    utils.execute('e2fsck', '-y', '-f', filename)
    utils.execute('resize2fs', '-F', '-M', filename)
    data = hu.parse_simple_kv('dumpe2fs', filename)
    block_count = int(data['block count'])
    block_size = int(data['block size'])
    with open(filename, 'rwb+') as f:
        f.truncate(block_count * block_size)


def add_apt_source(name, uri, suite, section, chroot):
    #TODO(agordeev): File names need to end with .list and may only contain
    # letters (a-z and A-Z), digits (0-9), underscore (_), hyphen (-) and
    # period (.) characters. Otherwise APT will ignore it.
    filename = 'fuel-image-{name}.list'.format(name=name)
    if section:
        entry = 'deb {uri} {suite} {section}\n'.format(uri=uri, suite=suite,
                                                       section=section)
    else:
        entry = 'deb {uri} {suite}\n'.format(uri=uri, suite=suite)
    with open(os.path.join(chroot, DEFAULT_APT_PATH['sources_dir'], filename),
              'w') as f:
        f.write(entry)


def add_apt_preference(name, priority, suite, section, chroot):
    #TODO(agordeev): The files have either no or "pref" as filename extension
    # and only contain alphanumeric, hyphen (-), underscore (_) and period (.)
    # characters.
    filename = 'fuel-image-{name}.pref'.format(name=name)
    #NOTE(agordeev): priotity=None means that there's no specific pinning for
    # particular repo and nothing to process.
    # Default system-wide preferences (priority=500) will be used instead.
    if priority:
        sections = section.split()
        with open(os.path.join(chroot, DEFAULT_APT_PATH['preferences_dir'],
                               filename), 'w') as f:
            f.write('Package: *\n')
            if sections:
                for section in sections:
                    f.write('Pin: release a={suite},c={section}\n'.format(
                        suite=suite, section=section))
            else:
                f.write('Pin: release a={suite}\n'.format(suite=suite))
            f.write('Pin-Priority: {priority}\n'.format(priority=priority))


#NOTE(agordeev): must be called prior run_apt_get
def pre_apt_get(chroot):
    clean_apt(chroot)
    #NOTE(agordeev): allow to install packages without gpg digest
    with open(os.path.join(chroot, DEFAULT_APT_PATH['conf_dir'],
                           CONF.allow_unsigned_file), 'w') as f:
        f.write('APT::Get::AllowUnauthenticated 1;\n')


def containerize(filename, container):
    if container == 'gzip':
        output_file = filename + '.gz'
        with open(filename, 'rb') as f:
            g = gzip.open(output_file, 'wb')
            for chunk in iter(lambda: f.read(CONF.data_chunk_size), ''):
                g.write(chunk)
            g.close()
        os.remove(filename)
        return output_file
    raise errors.WrongImageDataError(
        'Error while image initialization: '
        'unsupported image container: {container}'.format(container=container))
