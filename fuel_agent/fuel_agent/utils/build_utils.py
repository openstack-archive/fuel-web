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
import signal as sig
import stat
import tempfile
import time

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
    cfg.IntOpt(
        'fetch_packages_attempts',
        default=10,
        help='Maximum allowed debootstrap/apt-get attempts to execute'
    ),
    cfg.StrOpt(
        'allow_unsigned_file',
        default='allow_unsigned_packages',
        help='File where to store apt setting for unsigned packages'
    ),
    cfg.StrOpt(
        'force_ipv4_file',
        default='force_ipv4',
        help='File where to store apt setting for forcing IPv4 usage'
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


def run_debootstrap(uri, suite, chroot, arch='amd64', eatmydata=False,
                    attempts=CONF.fetch_packages_attempts):
    """Builds initial base system.

    debootstrap builds initial base system which is capable to run apt-get.
    debootstrap is well known for its glithcy resolving of package dependecies,
    so the rest of packages will be installed later by run_apt_get.
    """
    cmds = ['debootstrap', '--verbose', '--no-check-gpg', '--arch=%s' % arch,
            suite, chroot, uri]
    if eatmydata:
        cmds.insert(4, '--include=eatmydata')
    stdout, stderr = utils.execute(*cmds, attempts=attempts)
    LOG.debug('Running deboostrap completed.\nstdout: %s\nstderr: %s', stdout,
              stderr)


def set_apt_get_env():
    # NOTE(agordeev): disable any confirmations/questions from apt-get side
    os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
    os.environ['DEBCONF_NONINTERACTIVE_SEEN'] = 'true'
    os.environ['LC_ALL'] = os.environ['LANG'] = os.environ['LANGUAGE'] = 'C'


def run_apt_get(chroot, packages, eatmydata=False,
                attempts=CONF.fetch_packages_attempts):
    """Runs apt-get install <packages>.

    Unlike debootstrap, apt-get has a perfect package dependecies resolver
    under the hood.
    eatmydata could be used to totally ignore the storm of sync() calls from
    dpkg/apt-get tools. It's dangerous, but could decrease package install
    time in X times.
    """
    cmds = ['chroot', chroot, 'apt-get', '-y', 'update']
    stdout, stderr = utils.execute(*cmds, attempts=attempts)
    LOG.debug('Running apt-get update completed.\nstdout: %s\nstderr: %s',
              stdout, stderr)
    cmds = ['chroot', chroot, 'apt-get', '-y', 'install', ' '.join(packages)]
    if eatmydata:
        cmds.insert(2, 'eatmydata')
    stdout, stderr = utils.execute(*cmds, attempts=attempts)
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


def clean_dirs(chroot, dirs, delete=False):
    """Method is used to clean directories content
    or remove directories themselfs.

    :param chroot: Root directory where to look for subdirectories
    :param dirs: List of directories to clean/remove (Relative to chroot)
    :param delete: (Boolean) If True, directories will be removed
    (Default: False)
    """
    for d in dirs:
        path = os.path.join(chroot, d)
        if os.path.isdir(path):
            LOG.debug('Removing dir: %s', path)
            shutil.rmtree(path)
            if not delete:
                LOG.debug('Creating empty dir: %s', path)
                os.makedirs(path)


def remove_files(chroot, files):
    for f in files:
        path = os.path.join(chroot, f)
        if os.path.exists(path):
            os.remove(path)
            LOG.debug('Removed file: %s', path)


def clean_apt_settings(chroot, allow_unsigned_file=CONF.allow_unsigned_file,
                       force_ipv4_file=CONF.force_ipv4_file):
    """Cleans apt settings such as package sources and repo pinning."""
    files = [DEFAULT_APT_PATH['sources_file'],
             DEFAULT_APT_PATH['preferences_file'],
             os.path.join(DEFAULT_APT_PATH['conf_dir'], force_ipv4_file),
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
    # NOTE(agordeev): backport from bash-script:
    # in order to prevent the later puppet workflow outage, puppet service
    # should be disabled on a node startup.
    # Being enabled by default, sometimes it leads to puppet service hanging
    # and recognizing the deployment as failed.
    # TODO(agordeev): take care of puppet service for other distros, once
    # fuel-agent will be capable of building images for them too.
    utils.execute('chroot', chroot, 'update-rc.d', 'puppet', 'disable')
    # NOTE(agordeev): disable mcollective to be automatically started on boot
    # to prevent races between services which edit its server.cfg
    utils.execute('chroot', chroot, 'update-rc.d', 'mcollective', 'disable')
    # NOTE(agordeev): remove custom policy-rc.d which is needed to disable
    # execution of post/pre-install package hooks and start of services
    remove_files(chroot, ['usr/sbin/policy-rc.d'])
    clean_apt_settings(chroot)


def stop_chrooted_processes(chroot, signal=sig.SIGTERM,
                            attempts=10, attempts_delay=2):
    """Sends signal to all processes, which are running inside chroot.
    It tries several times until all processes die. If at some point there
    are no running processes found, it returns True.

    :param chroot: Process root directory.
    :param signal: Which signal to send to processes. It must be either
    SIGTERM or SIGKILL. (Default: SIGTERM)
    :param attempts: Number of attempts (Default: 10)
    :param attempts_delay: Delay between attempts (Default: 2)
    """

    if signal not in (sig.SIGTERM, sig.SIGKILL):
        raise ValueError('Signal must be either SIGTERM or SIGKILL')

    def get_running_processes():
        return utils.execute(
            'fuser', '-v', chroot, check_exit_code=False)[0].split()

    for i in six.moves.range(attempts):
        running_processes = get_running_processes()
        if not running_processes:
            LOG.debug('There are no running processes in %s ', chroot)
            return True
        for p in running_processes:
            try:
                pid = int(p)
                if os.readlink('/proc/%s/root' % pid) == chroot:
                    LOG.debug('Sending %s to chrooted process %s', signal, pid)
                    os.kill(pid, signal)
            except (OSError, ValueError) as e:
                cmdline = ''
                pid = p
                try:
                    with open('/proc/%s/cmdline' % pid) as f:
                        cmdline = f.read()
                except Exception:
                    LOG.debug('Can not read cmdline for pid=%s', pid)
                LOG.warning('Exception while sending signal: '
                            'pid: %s cmdline: %s message: %s. Skipping it.',
                            pid, cmdline, e)

        # First of all, signal delivery is asynchronous.
        # Just because the signal has been sent doesn't
        # mean the kernel will deliver it instantly
        # (the target process might be uninterruptible at the moment).
        # Secondly, exiting might take a while (the process might have
        # some data to fsync, etc)
        LOG.debug('Attempt %s. Waiting for %s seconds', i + 1, attempts_delay)
        time.sleep(attempts_delay)

    running_processes = get_running_processes()
    if running_processes:
        for pid in running_processes:
            cmdline = ''
            try:
                with open('/proc/%s/cmdline' % pid) as f:
                    cmdline = f.read()
            except Exception:
                LOG.debug('Can not read cmdline for pid=%s', pid)
            LOG.warning('Process is still running: pid=%s cmdline: %s',
                        pid, cmdline)
        return False
    return True


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


def deattach_loop(loop, check_exit_code=[0]):
    LOG.debug('Trying to figure out if loop device %s is attached', loop)
    output = utils.execute('losetup', '-a')[0]
    for line in output.split('\n'):
        # output lines are assumed to have the following format
        # /dev/loop0: [fd03]:130820 (/dev/loop0)
        if loop == line.split(':')[0]:
            LOG.debug('Loop device %s seems to be attached. '
                      'Trying to detach.', loop)
            utils.execute('losetup', '-d', loop,
                          check_exit_code=check_exit_code)


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
        sections = section.split()
        if sections:
            for s in sections:
                f.write('Package: *\n')
                f.write('Pin: release ')
                f.write(', '.join(conditions) + ", c={0}\n".format(s))
                f.write('Pin-Priority: {priority}\n'.format(priority=priority))
        else:
            f.write('Package: *\n')
            f.write('Pin: release ')
            f.write(', '.join(conditions) + "\n")
            f.write('Pin-Priority: {priority}\n'.format(priority=priority))


def pre_apt_get(chroot, allow_unsigned_file=CONF.allow_unsigned_file,
                force_ipv4_file=CONF.force_ipv4_file):
    """It must be called prior run_apt_get."""
    clean_apt_settings(chroot)
    # NOTE(agordeev): allow to install packages without gpg digest
    with open(os.path.join(chroot, DEFAULT_APT_PATH['conf_dir'],
                           allow_unsigned_file), 'w') as f:
        f.write('APT::Get::AllowUnauthenticated 1;\n')
    with open(os.path.join(chroot, DEFAULT_APT_PATH['conf_dir'],
                           force_ipv4_file), 'w') as f:
        f.write('Acquire::ForceIPv4 "true";\n')


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
