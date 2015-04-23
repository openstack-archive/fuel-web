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


class KernelScheme(object):
    def __init(self, kernel_name=None, initrd_name=None):
        self.kernel_name = kernel_name
        self.initrd_name = initrd_name

    def set_kernel(self, kernel_lt):
        if kernel_lt is not None:
            self.kernel_name = 'vmlinuz-3.10.55-1.mira4.x86_64'
            self.initrd_name = 'initramfs-3.10.55-1.mira4.x86_64.img'
        else:
            self.kernel_name = 'vmlinuz-2.6.32-504.1.3.el6.x86_64'
            self.initrd_name = 'initramfs-2.6.32-504.1.3.el6.x86_64.img'

    def kernel(self):
        return self 
