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

from fuel_agent import errors
from fuel_agent.openstack.common import log as logging
from fuel_agent.utils import hardware_utils as hu
from fuel_agent.utils import utils


LOG = logging.getLogger(__name__)


def mddetail_parse(output):
    md = {}
    h, v = output.split('Number   Major   Minor   RaidDevice State')
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


def mddisplay(names=[]):
    mdnames = names or get_mdnames()
    mds = []
    for mdname in mdnames:
        output = utils.execute('mdadm --detail %s' % mdname,
                               check_exit_code=[0])[0]
        md = {'name': mdname}
        md.update(mddetail_parse(output))
        mds.append(md)
    LOG.debug('Found md devices: {0}'.format(mds))
    return mds


def mdcreate(mdname, level, device, *args):
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
            set(reduce(lambda x, y: x + y, [md['devices'] for md in mds], [])):
        raise errors.MDDeviceDuplicationError(
            'Error while creating md: at least one of devices is '
            'already in belongs to some md')

    # cleaning md metadata from devices
    map(mdclean, devices)
    utils.execute('mdadm --create --force %s -e1.2 --level=%s '
                  '--raid-devices=%s %s' % (mdname, level, len(devices),
                                            ' '.join(devices)),
                  check_exit_code=[0])


def mdremove(mdname):
    mds = mddisplay()

    # check if md exists
    if not filter(lambda x: x['name'] == mdname, mds):
        raise errors.MDNotFoundError(
            'Error while removing md: md %s not found' % mdname)

    utils.execute('mdadm --stop %s' % mdname, check_exit_code=[0])
    utils.execute('mdadm --remove %s' % mdname, check_exit_code=[0, 1])


def mdclean(device):
    # we don't care if device actually exists or not
    utils.execute('mdadm --zero-superblock --force %s' % device,
                  check_exit_code=[0])
