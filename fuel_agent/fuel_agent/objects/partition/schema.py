# -*- coding: utf-8 -*-

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

from fuel_agent import errors
from fuel_agent.openstack.common import log as logging

from fuel_agent.objects.partition.fs import FileSystem
from fuel_agent.objects.partition.lv import LogicalVolume
from fuel_agent.objects.partition.md import MultipleDevice
from fuel_agent.objects.partition.parted import Parted
from fuel_agent.objects.partition.pv import PhysicalVolume
from fuel_agent.objects.partition.vg import VolumeGroup

LOG = logging.getLogger(__name__)


class PartitionScheme(object):
    def __init__(self):
        self.parteds = []
        self.mds = []
        self.pvs = []
        self.vgs = []
        self.lvs = []
        self.fss = []

    def add_parted(self, **kwargs):
        parted = Parted(**kwargs)
        self.parteds.append(parted)
        return parted

    def add_pv(self, **kwargs):
        pv = PhysicalVolume(**kwargs)
        self.pvs.append(pv)
        return pv

    def add_vg(self, **kwargs):
        vg = VolumeGroup(**kwargs)
        self.vgs.append(vg)
        return vg

    def add_lv(self, **kwargs):
        lv = LogicalVolume(**kwargs)
        self.lvs.append(lv)
        return lv

    def add_fs(self, **kwargs):
        fs = FileSystem(**kwargs)
        self.fss.append(fs)
        return fs

    def add_md(self, **kwargs):
        mdkwargs = {}
        mdkwargs['name'] = kwargs.get('name') or self.md_next_name()
        mdkwargs['level'] = kwargs.get('level') or 'mirror'
        md = MultipleDevice(**mdkwargs)
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

    def partition_by_name(self, name):
        return next((parted.partition_by_name(name)
                    for parted in self.parteds
                    if parted.partition_by_name(name)), None)

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

    def fs_sorted_by_depth(self, reverse=False):
        """Getting file systems sorted by path length.

        Shorter paths earlier.
        ['/', '/boot', '/var', '/var/lib/mysql']
        :param reverse: Sort backward (Default: False)
        """
        def key(x):
            return x.mount.rstrip(os.path.sep).count(os.path.sep)
        return sorted(self.fss, key=key, reverse=reverse)

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

    def to_dict(self):
        return {
            'parteds': [parted.to_dict() for parted in self.parteds],
            'mds': [md.to_dict() for md in self.mds],
            'pvs': [pv.to_dict() for pv in self.pvs],
            'vgs': [vg.to_dict() for vg in self.vgs],
            'lvs': [lv.to_dict() for lv in self.lvs],
            'fss': [fs.to_dict() for fs in self.fss],
        }
