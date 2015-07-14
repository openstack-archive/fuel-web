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

import re

from fuel_agent import errors
from fuel_agent.openstack.common import log as logging
from fuel_agent.utils import hardware as hu
from fuel_agent.utils import utils

LOG = logging.getLogger(__name__)


def mddetail_parse(output):
    md = {}
    # NOTE(agordeev): Somethimes 'State' column is missing
    h, _, v = re.split("Number\s+Major\s+Minor\s+RaidDevice\s+(State\s+)?",
                       output)
    for line in h.split('\n'):
        line = line.strip()
        if not line:
            continue
        for pattern in ('Version', 'Raid Level', 'Raid Devices',
                        'Active Devices', 'Spare Devices',
                        'Failed Devices', 'State', 'UUID'):
            if line.startswith(pattern):
                md[pattern] = line.split()[-1]
    md['devices'] = []
    for line in v.split('\n'):
        line = line.strip()
        if not line:
            continue
        md['devices'].append(line.split()[-1])
    return md


def get_mdnames(output=None):
    mdnames = []
    if not output:
        with open('/proc/mdstat') as f:
            output = f.read()
    for line in output.split('\n'):
        if line.startswith('md'):
            mdnames.append('/dev/%s' % line.split()[0])
    return mdnames


def mddisplay(names=None):
    mdnames = names or get_mdnames()
    mds = []
    for mdname in mdnames:
        md = {'name': mdname}
        try:
            output = utils.execute('mdadm', '--detail', mdname,
                                   check_exit_code=[0])[0]
            LOG.debug('mdadm --detail %s output:\n%s', mdname, output)
            md.update(mddetail_parse(output))
        except errors.ProcessExecutionError as exc:
            LOG.debug(exc)
            continue
        finally:
            mds.append(md)
    LOG.debug('Found md devices: {0}'.format(mds))
    return mds


def mdcreate(mdname, level, metadata, device, *args):
    supported_metadata = ('0', '0.90', '1', '1.0', '1.1', '1.2', 'default')
    if metadata not in supported_metadata:
        raise errors.MDWrongSpecError(
            'Error while creating md device: '
            'metadata must be one of %s' % ', '.join(supported_metadata))
    mds = mddisplay()

    # check if md device already exists
    if filter(lambda x: x['name'] == mdname, mds):
        raise errors.MDAlreadyExistsError(
            'Error while creating md: md %s already exists' % mdname)

    # check if level argument is valid
    supported_levels = ('0', '1', 'raid0', 'raid1', 'stripe', 'mirror')
    if level not in supported_levels:
        raise errors.MDWrongSpecError(
            'Error while creating md device: '
            'level must be one of: %s' % ', '.join(supported_levels))

    devices = [device] + list(args)

    # check if all necessary devices exist
    if not set(devices).issubset(
            set([bd['device'] for bd in hu.list_block_devices(disks=False)])):
        raise errors.MDNotFoundError(
            'Error while creating md: at least one of devices is not found')

    # check if devices are not parts of some md array
    if set(devices) & \
            set(reduce(lambda x, y: x + y,
                       [md.get('devices', []) for md in mds], [])):
        raise errors.MDDeviceDuplicationError(
            'Error while creating md: at least one of devices is '
            'already in belongs to some md')

    # FIXME: mdadm will ask user to continue creating if any device appears to
    #       be a part of raid array. Superblock zeroing helps to avoid that.
    map(mdclean, devices)
    utils.execute('mdadm', '--create', '--force', mdname, '-e', metadata,
                  '--level=%s' % level,
                  '--raid-devices=%s' % len(devices), *devices,
                  check_exit_code=[0])


def mdremove(mdname):
    # check if md exists
    if mdname not in get_mdnames():
        raise errors.MDNotFoundError(
            'Error while removing md: md %s not found' % mdname)
    # FIXME: The issue faced was quiet hard to reproduce and to figure out the
    #       root cause. For unknown reason already removed md device is
    #       unexpectedly returning back after a while from time to time making
    #       new md device creation to fail.
    #           Still the actual reason of its failure is unknown, but after a
    #       searching on a web a mention was found about a race in udev
    #       http://dev.bizo.com/2012/07/mdadm-device-or-resource-busy.html
    #       The article recommends to disable udev's queue entirely during md
    #       device manipulation which sounds rather unappropriate for our case.
    #       And the link to original post on mailing list suggests to execute
    #       `udevadm settle` before removing the md device.
    #       here -> http://permalink.gmane.org/gmane.linux.raid/34027
    #           So, what was done. `udevadm settle` calls were placed just
    #       before any of `mdadm` calls and the analizyng the logs was started.
    #       According to the manual `settle` is an option that "Watches the
    #       udev event queue, and exits if all current events are handled".
    #       That means it will wait for udev's finishing of processing the
    #       events. According to the logs noticeable delay had been recognized
    #       between `udevadm settle` and the next `mdadm` call.
    #           The delay was about 150-200ms or even bigger. It was appeared
    #       right before the `mdadm --stop` call. That just means that udev was
    #       too busy with events when we start to modifiy md devices hard.
    #           Thus `udevadm settle` is helping to avoid the later failure and
    #       to prevent strange behaviour of md device.
    utils.execute('udevadm', 'settle', '--quiet', check_exit_code=[0])
    utils.execute('mdadm', '--stop', mdname, check_exit_code=[0])
    utils.execute('mdadm', '--remove', mdname, check_exit_code=[0, 1])


def mdclean(device):
    # we don't care if device actually exists or not
    utils.execute('mdadm', '--zero-superblock', '--force', device,
                  check_exit_code=[0])


def mdclean_all():
    LOG.debug('Trying to wipe out all md devices')
    for md in mddisplay():
        mdremove(md['name'])
        for dev in md.get('devices', []):
            mdclean(dev)
    # second attempt, remove stale inactive devices
    for md in mddisplay():
        mdremove(md['name'])
    mds = mddisplay()
    if len(mds) > 0:
        raise errors.MDRemovingError(
            'Error while removing mds: few devices still presented %s' % mds)
