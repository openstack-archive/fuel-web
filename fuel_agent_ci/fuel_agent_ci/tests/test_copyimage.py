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
import mock

from fuel_agent import manager as fa_manager
from fuel_agent.utils import hardware_utils as hu
from fuel_agent_ci.tests import utils as tu
from fuel_agent.utils import utils

from oslo.config import cfg


CONF = cfg.CONF


class TestConfigDriver(tu.BaseFuelAgentCITest):
    def _test_copyimage(self, mock_lbd, profile):
        p_data = tu.get_filled_provision_data(self.dhcp_hosts[0]['ip'],
                                              self.dhcp_hosts[0]['mac'],
                                              self.net.ip, self.http_obj.port,
                                              profile)
        self.env.ssh_by_name(self.name).put_content(
            json.dumps(p_data), os.path.join('/tmp', 'provision.json'))
        self.env.ssh_by_name(self.name).run(
            'partition', command_timeout=tu.SSH_COMMAND_TIMEOUT)
        self.env.ssh_by_name(self.name).run(
            'copyimage', command_timeout=tu.SSH_COMMAND_TIMEOUT)
        hu_lbd = self.env.ssh_by_name(self.name).run(
            'python -c "from fuel_agent.utils import hardware_utils as hu;'
            'import json; print json.dumps(hu.list_block_devices())"',
            command_timeout=tu.SSH_COMMAND_TIMEOUT)
        mock_lbd.return_value = json.loads(hu_lbd)
        self.mgr = fa_manager.Manager(p_data)
        self.mgr.do_parsing()
        local_img_path = os.path.join(self.env.envdir, self.http_obj.http_root,
                                      profile, profile + '.img.gz')
        md5sum_output = utils.execute('gunzip -cd %s|md5sum' % local_img_path)
        img_size_output = utils.execute('gzip -ql %s' % local_img_path)
        img_size = int(
            [s.strip() for s in img_size_output[0].split(' ') if s.strip()][1]
        ) / 2 ** 20
        expected_md5 = md5sum_output[0].split(' ')[0]
        img = self.mgr.image_scheme.images[-1]
        md5sum_metadata_output = self.env.ssh_by_name(self.name).run(
            'dd if=%s bs=1M count=%s | md5sum' % (img.target_device, img_size),
            command_timeout=tu.SSH_COMMAND_TIMEOUT)
        actual_md5 = md5sum_metadata_output.split(' ')[0]
        self.assertEqual(expected_md5, actual_md5)

    @mock.patch.object(hu, 'list_block_devices')
    def test_copyimage_centos(self, mock_lbd):
        self._test_copyimage(mock_lbd, 'centos')

    @mock.patch.object(hu, 'list_block_devices')
    def test_copyimage_ubuntu(self, mock_lbd):
        self._test_copyimage(mock_lbd, 'ubuntu')
