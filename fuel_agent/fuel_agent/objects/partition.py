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

LOG = logging.getLogger(__name__)


class Parted(object):
    def __init__(self, name, label):
        self.name = name
        self.label = label
        self.partitions = []
        self.install_bootloader = False

    def add_partition(self, **kwargs):
        # TODO(kozhukalov): validate before appending
        # calculating partition name based on device name and partition count
        kwargs['name'] = self.next_name()
        kwargs['count'] = self.next_count()
        kwargs['device'] = self.name
        # if begin is given use its value else use end of last partition
        kwargs['begin'] = kwargs.get('begin', self.next_begin())
        # if end is given use its value else
        # try to calculate it based on size kwarg or
        # raise KeyError
        # (kwargs.pop['size'] will raise error if size is not set)
        kwargs['end'] = kwargs.get('end') or \
            kwargs['begin'] + kwargs.pop('size')
        # if partition_type is given use its value else
        # try to calculate it automatically
        kwargs['partition_type'] = \
            kwargs.get('partition_type', self.next_type())
        partition = Partition(**kwargs)
        self.partitions.append(partition)
        return partition

    @property
    def logical(self):
        return filter(lambda x: x.type == 'logical', self.partitions)

    @property
    def primary(self):
        return filter(lambda x: x.type == 'primary', self.partitions)

    @property
    def extended(self):
        found = filter(lambda x: x.type == 'extended', self.partitions)
        if found:
            return found[0]

    def next_type(self):
        if self.label == 'gpt':
            return 'primary'
        elif self.label == 'msdos':
            if self.extended:
                return 'logical'
            elif len(self.partitions) < 3 and not self.extended:
                return 'primary'
            elif len(self.partitions) == 3 and not self.extended:
                return 'extended'
            #NOTE(agordeev): how to reach that condition?
            else:
                return 'logical'

    def next_count(self, next_type=None):
        next_type = next_type or self.next_type()
        if next_type == 'logical':
            return len(self.logical) + 5
        return len(self.partitions) + 1

    def next_begin(self):
        if not self.partitions:
            return 1
        if self.partitions[-1] == self.extended:
            return self.partitions[-1].begin
        return self.partitions[-1].end

    def next_name(self):
        if self.next_type() == 'extended':
            return None
        separator = ''
        if 'cciss' in self.name or 'loop' in self.name:
            separator = 'p'
        return '%s%s%s' % (self.name, separator, self.next_count())


class Partition(object):
    def __init__(self, name, count, device, begin, end, partition_type,
                 flags=None, guid=None, configdrive=False):
        self.name = name
        self.count = count
        self.device = device
        self.name = name
        self.begin = begin
        self.end = end
        self.type = partition_type
        self.flags = flags or []
        self.guid = guid
        self.configdrive = configdrive

    def set_flag(self, flag):
        if flag not in self.flags:
            self.flags.append(flag)

    def set_guid(self, guid):
        self.guid = guid


class Pv(object):
    def __init__(self, name, metadatasize=16, metadatacopies=2):
        self.name = name
        self.metadatasize = metadatasize
        self.metadatacopies = metadatacopies


class Vg(object):
    def __init__(self, name, pvnames=None):
        self.name = name
        self.pvnames = pvnames or []

    def add_pv(self, pvname):
        if pvname not in self.pvnames:
            self.pvnames.append(pvname)


class Lv(object):
    def __init__(self, name, vgname, size):
        self.name = name
        self.vgname = vgname
        self.size = size

    @property
    def device_name(self):
        return '/dev/mapper/%s-%s' % (self.vgname.replace('-', '--'),
                                      self.name.replace('-', '--'))


class Md(object):
    def __init__(self, name, level,
                 devices=None, spares=None):
        self.name = name
        self.level = level
        self.devices = devices or []
        self.spares = spares or []

    def add_device(self, device):
        if device in self.devices or device in self.spares:
            raise errors.MDDeviceDuplicationError(
                'Error while attaching device to md: '
                'device %s is already attached' % device)
        self.devices.append(device)

    def add_spare(self, device):
        if device in self.devices or device in self.spares:
            raise errors.MDDeviceDuplicationError(
                'Error while attaching device to md: '
                'device %s is already attached' % device)
        self.spares.append(device)


class Fs(object):
    def __init__(self, device, mount=None,
                 fs_type=None, fs_options=None, fs_label=None):
        self.device = device
        self.mount = mount
        self.type = fs_type or 'xfs'
        self.options = fs_options or ''
        self.label = fs_label or ''


class PartitionScheme(object):
    def __init__(self):
        self.parteds = []
        self.mds = []
        self.pvs = []
        self.vgs = []
        self.lvs = []
        self.fss = []
        self.kernel_params = ''

    def add_parted(self, **kwargs):
        parted = Parted(**kwargs)
        self.parteds.append(parted)
        return parted

    def add_pv(self, **kwargs):
        pv = Pv(**kwargs)
        self.pvs.append(pv)
        return pv

    def add_vg(self, **kwargs):
        vg = Vg(**kwargs)
        self.vgs.append(vg)
        return vg

    def add_lv(self, **kwargs):
        lv = Lv(**kwargs)
        self.lvs.append(lv)
        return lv

    def add_fs(self, **kwargs):
        fs = Fs(**kwargs)
        self.fss.append(fs)
        return fs

    def add_md(self, **kwargs):
        mdkwargs = {}
        mdkwargs['name'] = kwargs.get('name') or self.md_next_name()
        mdkwargs['level'] = kwargs.get('level') or 'mirror'
        md = Md(**mdkwargs)
        self.mds.append(md)
        return md

    def md_by_name(self, name):
        found = filter(lambda x: x.name == name, self.mds)
        if found:
            return found[0]

    def md_by_mount(self, mount):
        fs = self.fs_by_mount(mount)
        if fs:
            return self.md_by_name(fs.device)

    def md_attach_by_mount(self, device, mount, spare=False, **kwargs):
        md = self.md_by_mount(mount)
        if not md:
            md = self.add_md(**kwargs)
            fskwargs = {}
            fskwargs['device'] = md.name
            fskwargs['mount'] = mount
            fskwargs['fs_type'] = kwargs.pop('fs_type', None)
            fskwargs['fs_options'] = kwargs.pop('fs_options', None)
            fskwargs['fs_label'] = kwargs.pop('fs_label', None)
            self.add_fs(**fskwargs)
        md.add_spare(device) if spare else md.add_device(device)
        return md

    def md_next_name(self):
        count = 0
        while True:
            name = '/dev/md%s' % count
            if name not in [md.name for md in self.mds]:
                return name
            if count >= 127:
                raise errors.MDAlreadyExistsError(
                    'Error while generating md name: '
                    'names from /dev/md0 to /dev/md127 seem to be busy, '
                    'try to generate md name manually')
            count += 1

    def vg_by_name(self, vgname):
        found = filter(lambda x: (x.name == vgname), self.vgs)
        if found:
            return found[0]

    def pv_by_name(self, pvname):
        found = filter(lambda x: (x.name == pvname), self.pvs)
        if found:
            return found[0]

    def vg_attach_by_name(self, pvname, vgname,
                          metadatasize=16, metadatacopies=2):
        vg = self.vg_by_name(vgname) or self.add_vg(name=vgname)
        pv = self.pv_by_name(pvname) or self.add_pv(
            name=pvname, metadatasize=metadatasize,
            metadatacopies=metadatacopies)
        vg.add_pv(pv.name)

    def fs_by_mount(self, mount):
        found = filter(lambda x: (x.mount and x.mount == mount), self.fss)
        if found:
            return found[0]

    def fs_by_device(self, device):
        found = filter(lambda x: x.device == device, self.fss)
        if found:
            return found[0]

    def lv_by_device_name(self, device_name):
        found = filter(lambda x: x.device_name == device_name, self.lvs)
        if found:
            return found[0]

    def root_device(self):
        fs = self.fs_by_mount('/')
        if not fs:
            raise errors.WrongPartitionSchemeError(
                'Error while trying to find root device: '
                'root file system not found')
        return fs.device

    def boot_device(self, grub_version=2):
        # We assume /boot is a separate partition. If it is not
        # then we try to use root file system
        boot_fs = self.fs_by_mount('/boot') or self.fs_by_mount('/')
        if not boot_fs:
            raise errors.WrongPartitionSchemeError(
                'Error while trying to find boot device: '
                'boot file system not fount, '
                'it must be a separate mount point')

        if grub_version == 1:
            # Legacy GRUB has a limitation. It is not able to mount MD devices.
            # If it is MD compatible it is only able to ignore MD metadata
            # and to mount one of those devices which are parts of MD device,
            # but it is possible only if MD device is a MIRROR.
            md = self.md_by_name(boot_fs.device)
            if md:
                try:
                    return md.devices[0]
                except IndexError:
                    raise errors.WrongPartitionSchemeError(
                        'Error while trying to find boot device: '
                        'md device %s does not have devices attached' %
                        md.name)
            # Legacy GRUB is not able to mount LVM devices.
            if self.lv_by_device_name(boot_fs.device):
                raise errors.WrongPartitionSchemeError(
                    'Error while trying to find boot device: '
                    'found device is %s but legacy grub is not able to '
                    'mount logical volumes' %
                    boot_fs.device)

        return boot_fs.device

    def configdrive_device(self):
        # Configdrive device must be a small (about 10M) partition
        # on one of node hard drives. This partition is necessary
        # only if one uses cloud-init with configdrive.
        for parted in self.parteds:
            for prt in parted.partitions:
                if prt.configdrive:
                    return prt.name

    def append_kernel_params(self, kernel_params):
        self.kernel_params += ' ' + kernel_params
