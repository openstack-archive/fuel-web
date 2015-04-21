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
import re
import shutil
import stat
import tempfile

import six
import yaml

from oslo.config import cfg

from fuel_agent import errors
from fuel_agent.openstack.common import log as logging
from fuel_agent.utils import hardware_utils as hu
from fuel_agent.utils import utils

LOG = logging.getLogger(__name__)

bu_opts = [
    cfg.IntOpt(
        'max_loop_devices_count',
        default=255,
        # NOTE(agordeev): up to 256 loop devices could be allocated up to
        # kernel version 2.6.23, and the limit (from version 2.6.24 onwards)
        # isn't theoretically present anymore.
        help='Maximum allowed loop devices count to use'
    ),
    cfg.IntOpt(
        'sparse_file_size',
        default=2048,
        help='Size of sparse file in MiBs'
    ),
    cfg.IntOpt(
        'loop_device_major_number',
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
# NOTE(agordeev): hardcoded to r00tme
ROOT_PASSWORD = '$6$IInX3Cqo$5xytL1VZbZTusOewFnG6couuF0Ia61yS3rbC6P5YbZP2TYcl'\
                'wHqMq9e3Tg8rvQxhxSlBXP1DZhdUamxdOBXK0.'


def run_debootstrap(uri, suite, chroot, arch='amd64', eatmydata=False):
    """Builds initial base system.

    debootstrap builds initial base system which is capable to run apt-get.
    debootstrap is well known for its glithcy resolving of package dependecies,
    so the rest of packages will be installed later by run_apt_get.
    """
    # TODO(agordeev): do retry!
    cmds = ['debootstrap', '--verbose', '--no-check-gpg', '--arch=%s' % arch,
            suite, chroot, uri]
    if eatmydata:
        cmds.insert(4, '--include=eatmydata')
    stdout, stderr = utils.execute(*cmds)
    LOG.debug('Running deboostrap completed.\nstdout: %s\nstderr: %s', stdout,
              stderr)


def set_apt_get_env():
    # NOTE(agordeev): disable any confirmations/questions from apt-get side
    os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
    os.environ['DEBCONF_NONINTERACTIVE_SEEN'] = 'true'
    os.environ['LC_ALL'] = os.environ['LANG'] = os.environ['LANGUAGE'] = 'C'


def run_apt_get(chroot, packages, eatmydata=False):
    """Runs apt-get install <packages>.

    Unlike debootstrap, apt-get has a perfect package dependecies resolver
    under the hood.
    eatmydata could be used to totally ignore the storm of sync() calls from
    dpkg/apt-get tools. It's dangerous, but could decrease package install
    time in X times.
    """
    # TODO(agordeev): do retry!
    cmds = ['chroot', chroot, 'apt-get', '-y', 'update']
    stdout, stderr = utils.execute(*cmds)
    LOG.debug('Running apt-get update completed.\nstdout: %s\nstderr: %s',
              stdout, stderr)
    cmds = ['chroot', chroot, 'apt-get', '-y', 'install', ' '.join(packages)]
    if eatmydata:
        cmds.insert(2, 'eatmydata')
    stdout, stderr = utils.execute(*cmds)
    LOG.debug('Running apt-get install completed.\nstdout: %s\nstderr: %s',
              stdout, stderr)


def suppress_services_start(chroot):
    """Suppresses services start.

    Prevents start of any service such as udev/ssh/etc in chrooted environment
    while image is being built.
    """
    path = os.path.join(chroot, 'usr/sbin')
    if not os.path.exists(path):
        os.makedirs(path)
    with open(os.path.join(path, 'policy-rc.d'), 'w') as f:
        f.write('#!/bin/sh\n'
                '# prevent any service from being started\n'
                'exit 101\n')
        os.fchmod(f.fileno(), 0o755)


def clean_dirs(chroot, dirs):
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


def clean_apt_settings(chroot, allow_unsigned_file=CONF.allow_unsigned_file):
    """Cleans apt settings such as package sources and repo pinning."""
    files = [DEFAULT_APT_PATH['sources_file'],
             DEFAULT_APT_PATH['preferences_file'],
             os.path.join(DEFAULT_APT_PATH['conf_dir'], allow_unsigned_file)]
    remove_files(chroot, files)
    dirs = [DEFAULT_APT_PATH['preferences_dir'],
            DEFAULT_APT_PATH['sources_dir']]
    clean_dirs(chroot, dirs)


def do_post_inst(chroot):
    # NOTE(agordeev): set up password for root
    utils.execute('sed', '-i',
                  's%root:[\*,\!]%root:' + ROOT_PASSWORD + '%',
                  os.path.join(chroot, 'etc/shadow'))
    # NOTE(agordeev): remove custom policy-rc.d which is needed to disable
    # execution of post/pre-install package hooks and start of services
    remove_files(chroot, ['usr/sbin/policy-rc.d'])
    clean_apt_settings(chroot)


def send_signal_to_chrooted_processes(chroot, signal):
    """Sends signal to all processes, which are running inside of chroot."""
    for p in utils.execute('fuser', '-v', chroot,
                           check_exit_code=False)[0].split():
        try:
            pid = int(p)
            if os.readlink('/proc/%s/root' % pid) == chroot:
                LOG.debug('Sending %s to chrooted process %s', signal, pid)
                os.kill(pid, signal)
        except (OSError, ValueError):
            LOG.warning('Skipping non pid %s from fuser output' % p)


def get_free_loop_device(
        loop_device_major_number=CONF.loop_device_major_number,
        max_loop_devices_count=CONF.max_loop_devices_count):
    """Returns the name of free loop device.

    It should return the name of free loop device or raise an exception.
    Unfortunately, free loop device couldn't be reversed for the later usage,
    so we must start to use it as fast as we can.
    If there's no free loop it will try to create new one and ask a system for
    free loop again.
    """
    for minor in range(0, max_loop_devices_count):
        cur_loop = "/dev/loop%s" % minor
        if not os.path.exists(cur_loop):
            os.mknod(cur_loop, 0o660 | stat.S_IFBLK,
                     os.makedev(loop_device_major_number, minor))
        try:
            return utils.execute('losetup', '--find')[0].split()[0]
        except (IndexError, errors.ProcessExecutionError):
            LOG.debug("Couldn't find free loop device, trying again")
    raise errors.NoFreeLoopDevices('Free loop device not found')


def create_sparse_tmp_file(dir, suffix, size=CONF.sparse_file_size):
    """Creates sparse file.

    Creates file which consumes disk space more efficiently when the file
    itself is mostly empty.
    """
    tf = tempfile.NamedTemporaryFile(dir=dir, suffix=suffix, delete=False)
    utils.execute('truncate', '-s', '%sM' % size, tf.name)
    return tf.name


def attach_file_to_loop(filename, loop):
    utils.execute('losetup', loop, filename)


def deattach_loop(loop):
    utils.execute('losetup', '-d', loop)


def shrink_sparse_file(filename):
    """Shrinks file to its size of actual data. Only ext fs are supported."""
    utils.execute('e2fsck', '-y', '-f', filename)
    utils.execute('resize2fs', '-F', '-M', filename)
    data = hu.parse_simple_kv('dumpe2fs', filename)
    block_count = int(data['block count'])
    block_size = int(data['block size'])
    with open(filename, 'rwb+') as f:
        f.truncate(block_count * block_size)


def strip_filename(name):
    """Strips filename for apt settings.

    The name could only contain alphanumeric, hyphen (-), underscore (_) and
    period (.) characters.
    """
    return re.sub(r"[^a-zA-Z0-9-_.]*", "", name)


def get_release_file(uri, suite, section):
    """Download repo's Release file, parse it and returns an apt
    preferences line for this repo.

    :param repo: a repo as dict
    :returns: a string with apt preferences rules
    """
    if section:
        # We can't use urljoin here because it works pretty bad in
        # cases when 'uri' doesn't have a trailing slash.
        download_uri = os.path.join(uri, 'dists', suite, 'Release')
    else:
        # Well, we have a flat repo case, so we should download Release
        # file from a different place. Please note, we have to strip
        # a leading slash from suite because otherwise the download
        # link will be wrong.
        download_uri = os.path.join(uri, suite.lstrip('/'), 'Release')

    return utils.init_http_request(download_uri).text


def parse_release_file(content):
    """Parse Debian repo's Release file content.

    :param content: a Debian's Release file content
    :returns: a dict with repo's attributes
    """
    _multivalued_fields = {
        'SHA1': ['sha1', 'size', 'name'],
        'SHA256': ['sha256', 'size', 'name'],
        'SHA512': ['sha512', 'size', 'name'],
        'MD5Sum': ['md5sum', 'size', 'name'],
    }

    # debian data format is very similiar to yaml, except
    # multivalued field. so we can parse it just like yaml
    # and then perform additional transformation for those
    # fields (we know which ones are multivalues).
    data = yaml.load(content)

    for attr, columns in six.iteritems(_multivalued_fields):
        if attr not in data:
            continue

        values = data[attr].split()
        data[attr] = []

        for group in utils.grouper(values, len(columns)):
            data[attr].append(dict(zip(columns, group)))

    return data


def add_apt_source(name, uri, suite, section, chroot):
    # NOTE(agordeev): The files have either no or "list" as filename extension
    filename = 'fuel-image-{name}.list'.format(name=strip_filename(name))
    if section:
        entry = 'deb {uri} {suite} {section}\n'.format(uri=uri, suite=suite,
                                                       section=section)
    else:
        entry = 'deb {uri} {suite}\n'.format(uri=uri, suite=suite)
    with open(os.path.join(chroot, DEFAULT_APT_PATH['sources_dir'], filename),
              'w') as f:
        f.write(entry)


def add_apt_preference(name, priority, suite, section, chroot, uri):
    # NOTE(agordeev): The files have either no or "pref" as filename extension
    filename = 'fuel-image-{name}.pref'.format(name=strip_filename(name))
    # NOTE(agordeev): priotity=None means that there's no specific pinning for
    # particular repo and nothing to process.
    # Default system-wide preferences (priority=500) will be used instead.

    _transformations = {
        'Archive': 'a',
        'Suite': 'a',       # suite is a synonym for archive
        'Codename': 'n',
        'Version': 'v',
        'Origin': 'o',
        'Label': 'l',
    }

    try:
        deb_release = parse_release_file(
            get_release_file(uri, suite, section)
        )
    except ValueError as exc:
        LOG.error(
            "[Attention] Failed to fetch Release file "
            "for repo '{0}': {1} - skipping. "
            "This may lead both to trouble with packages "
            "and broken OS".format(name, six.text_type(exc))
        )
        return

    conditions = set()
    for field, condition in six.iteritems(_transformations):
        if field in deb_release:
            conditions.add(
                '{0}={1}'.format(condition, deb_release[field])
            )

    with open(os.path.join(chroot, DEFAULT_APT_PATH['preferences_dir'],
                           filename), 'w') as f:
        f.write('Package: *\n')
        for s in section.split():
            f.write('Pin: release ')
            f.write(', '.join(conditions) + ", c={0}\n".format(s))
        f.write('Pin-Priority: {priority}\n'.format(priority=priority))


def pre_apt_get(chroot, allow_unsigned_file=CONF.allow_unsigned_file):
    """It must be called prior run_apt_get."""
    clean_apt_settings(chroot)
    # NOTE(agordeev): allow to install packages without gpg digest
    with open(os.path.join(chroot, DEFAULT_APT_PATH['conf_dir'],
                           allow_unsigned_file), 'w') as f:
        f.write('APT::Get::AllowUnauthenticated 1;\n')


def containerize(filename, container, chunk_size=CONF.data_chunk_size):
    if container == 'gzip':
        output_file = filename + '.gz'
        with open(filename, 'rb') as f:
            # NOTE(agordeev): gzip in python2.6 doesn't have context manager
            # support
            g = gzip.open(output_file, 'wb')
            for chunk in iter(lambda: f.read(chunk_size), ''):
                g.write(chunk)
            g.close()
        os.remove(filename)
        return output_file
    raise errors.WrongImageDataError(
        'Error while image initialization: '
        'unsupported image container: {container}'.format(container=container))
