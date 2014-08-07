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

import json
import os

from fuel_agent_ci.tests import base
from fuel_agent.utils import utils

TARGET_DEVICE = '/dev/mapper/os-root'


class TestCopyImage(base.BaseFuelAgentCITest):
    def _test_copyimage(self, profile):
        #NOTE(agordeev): update provision.json with proper image specs
        p_data = base.get_filled_provision_data(self.dhcp_hosts[0]['ip'],
                                                self.dhcp_hosts[0]['mac'],
                                                self.net.ip,
                                                self.http_obj.port, profile)
        self.env.ssh_by_name(self.name).put_content(
            json.dumps(p_data), os.path.join('/tmp', 'provision.json'))
        #NOTE(agordeev): disks should be partitioned before applying the image
        self.env.ssh_by_name(self.name).run(
            'partition', command_timeout=base.SSH_COMMAND_TIMEOUT)
        self.env.ssh_by_name(self.name).run(
            'copyimage', command_timeout=base.SSH_COMMAND_TIMEOUT)
        #NOTE(agordeev): size and checksum needed for checking deployed image
        local_img_path = os.path.join(self.env.envdir, self.http_obj.http_root,
                                      profile, profile + '.img.gz')
        md5sum_output = utils.execute('gunzip', '-cd', local_img_path, '|',
                                      'md5sum')
        img_size_output = utils.execute('gzip', '-ql', local_img_path)
        img_size = int(img_size_output[0].split()[1]) / 2 ** 20
        expected_md5 = md5sum_output[0].split()[0]
        #NOTE(agordeev): the partition can be bigger than actual size of image
        #                so calculating checksum of rewritten partition part
        #                assuming that image has size in MB w/o fractional part
        md5sum_metadata_output = self.env.ssh_by_name(self.name).run(
            'dd if=%s bs=1M count=%s | md5sum' % (TARGET_DEVICE, img_size),
            command_timeout=base.SSH_COMMAND_TIMEOUT)
        actual_md5 = md5sum_metadata_output.split()[0]
        self.assertEqual(expected_md5, actual_md5)

    def test_copyimage_centos(self):
        self._test_copyimage('centos')

    def test_copyimage_ubuntu(self):
        self._test_copyimage('ubuntu')
