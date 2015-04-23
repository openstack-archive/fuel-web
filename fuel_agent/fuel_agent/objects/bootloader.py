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
    def __init__(self, version=None, kernel_params='',
                 kernel_name=None, kernel_regexp=None,
                 initrd_name=None, initrd_regexp=None):
        self.version = version
        self.kernel_params = kernel_params
        self.kernel_name = kernel_name
        self.initrd_name = initrd_name
        self.kernel_regexp = kernel_regexp
        self.initrd_regexp = initrd_regexp

    def append_kernel_params(self, *kernel_params):
        for kp in kernel_params:
            self.kernel_params = '{0} {1}'.format(self.kernel_params, kp)
