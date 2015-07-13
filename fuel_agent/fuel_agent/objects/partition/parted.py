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

import copy

from fuel_agent.objects import base


class Parted(base.Serializable):

    def __init__(self, name, label, partitions=None):
        self.name = name
        self.label = label
        self.partitions = partitions or []
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
            # NOTE(agordeev): how to reach that condition?
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
        special_devices = ('cciss', 'nvme', 'loop')
        if any(n in self.name for n in special_devices):
            separator = 'p'
        return '%s%s%s' % (self.name, separator, self.next_count())

    def partition_by_name(self, name):
        found = filter(lambda x: (x.name == name), self.partitions)
        if found:
            return found[0]

    def to_dict(self):
        partitions = [partition.to_dict() for partition in self.partitions]
        return {
            'name': self.name,
            'label': self.label,
            'partitions': partitions,
        }

    @classmethod
    def from_dict(cls, data):
        data = copy.deepcopy(data)
        raw_partitions = data.pop('partitions')
        partitions = [Partition.from_dict(partition)
                      for partition in raw_partitions]
        return cls(partitions=partitions, **data)


class Partition(base.BasePartition):

    def __init__(self, name, count, device, begin, end, partition_type,
                 flags=None, guid=None, configdrive=False, **kwargs):
        super(Partition, self).__init__(**kwargs)
        self.name = name
        self.count = count
        self.device = device
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

    def to_dict(self):
        data = super(Partition, self).to_dict()
        data.update({
            'name': self.name,
            'count': self.count,
            'device': self.device,
            'begin': self.begin,
            'end': self.end,
            'partition_type': self.type,
            'flags': self.flags,
            'guid': self.guid,
            'configdrive': self.configdrive,
        })
        return data
