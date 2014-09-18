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
import time

from fuel_agent_ci.tests import base
from fuel_agent_ci import utils


class TestCopyImage(base.BaseFuelAgentCITest):
    def _test_copyimage(self, profile):
        #NOTE(agordeev): update provision.json with proper image specs
        provision_data = json.loads(self.render_template(
            template_data={
                'IP': self.dhcp_hosts[0]['ip'],
                'MAC': self.dhcp_hosts[0]['mac'],
                'MASTER_IP': self.net.ip,
                'MASTER_HTTP_PORT': self.http.port,
                'PROFILE': profile
            },
            template_name='provision.json'
        ))
        self.ssh.put_content(json.dumps(provision_data), '/tmp/provision.json')
        #NOTE(agordeev): disks should be partitioned before applying the image
        self.ssh.run('partition')
        self.ssh.run('copyimage')
        #NOTE(agordeev): size and checksum needed for checking deployed image
        local_img_path = os.path.join(
            self.env.envdir, self.http.http_root, profile + '.img.gz')
        expected_md5 = str(utils.execute(
            'gunzip -cd %s | md5sum' % local_img_path)).split()[0]
        img_size = int(str(utils.execute(
            'gzip -ql %s' % local_img_path)).split()[1]) / 2 ** 20

        #NOTE(agordeev): the partition can be bigger than actual size of image
        #                so calculating checksum of rewritten partition part
        #                assuming that image has size in MB w/o fractional part
        actual_md5 = self.ssh.run(
            'dd if=%s bs=1M count=%s | md5sum' %
            ('/dev/mapper/os-root', img_size)).split()[0]

        self.assertEqual(expected_md5, actual_md5)

    def test_copyimage_centos(self):
        self._test_copyimage('centos_65_x86_64')

    def test_copyimage_ubuntu(self):
        self._test_copyimage('ubuntu_1204_x86_64')
