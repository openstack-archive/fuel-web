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


class Grub(object):
    def __init__(self, version=1, kernel_name='vmlinuz',
                 initrd_name='initramfs', kernel_params='',
                 kernel_version='2.6'):
        self.version = version
        self.kernel_name = kernel_name
        self.initrd_name = initrd_name
        self.kernel_params = ''
        self.kernel_version = kernel_version

    def append_kernel_params(self, kernel_params):
        self.kernel_params += ' ' + kernel_params

    def get_regexp(self):
        kernel_version = self.kernel_version.replace('.', '\.')
        kernel_version_regex = "-%s\.\d+" % kernel_version
        return { "kernel_name" : self.kernel_name,
                 "initrd_name" : self.initrd_name,
                 "kernel_version" : kernel_version_regex }

    def grub(self):
        return self
