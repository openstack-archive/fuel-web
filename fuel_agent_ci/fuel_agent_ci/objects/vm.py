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


class Vm(object):
    def __init__(self, name, boot=None):
        self.name = name
        self.interfaces = []
        self.disks = []
        self.boot = boot or 'hd'

    def add_interface(self, **kwargs):
        if 'interface' in kwargs:
            interface = kwargs['interface']
        else:
            interface = Interface(**kwargs)
        self.interfaces.append(interface)
        return interface

    def add_disk(self, **kwargs):
        if 'disk' in kwargs:
            disk = kwargs['disk']
        else:
            disk = Disk(**kwargs)
        self.disks.append(disk)
        return disk


class Interface(object):
    def __init__(self, mac, network):
        self.mac = mac
        self.network = network


class Disk(object):
    def __init__(self, size=None, base=None):
        self.size = size
        self.base = base
