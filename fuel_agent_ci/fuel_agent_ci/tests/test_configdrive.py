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

import hashlib
import json
import os
import mock

#TODO(agordeev): remove fuel_agent requirement when configdrive artefact
#                will become ready
from fuel_agent.utils import hardware_utils as hu
from fuel_agent_ci.tests import utils as tu


TEMPLATE_PATH = '/usr/share/fuel-agent/cloud-init-templates'
CONFIG_DRIVE_PATH = '/tmp/config-drive.img'
TMP_PATH = '/tmp'


class TestConfigDrive(tu.BaseFuelAgentCITest):
    def setUp(self):
        super(TestConfigDrive, self).setUp()
        #FIXME(agordeev): fuel_agent package isn't ready,
        #                 so copying templates to TEMPLATE_PATH dir
        self.env.ssh_by_name(self.name).run(
            'mkdir -p %s' % TEMPLATE_PATH)
        self.env.ssh_by_name(self.name).run(
            "find /root/var/tmp/fuel_agent_ci/fuel_agent -name '*jinja2' -exec"
            " cp '{}' %s \;" % TEMPLATE_PATH)
        self.env.ssh_by_name(self.name).run(
            'configdrive', command_timeout=tu.SSH_COMMAND_TIMEOUT)

    @mock.patch.object(hu, 'list_block_devices')
    def test_config_driver(self, mock_lbd):
        def _get_md5sum(file_path, size=-1):
            md5 = None
            with open(file_path) as f:
                md5 = hashlib.md5(f.read(size)).hexdigest()
            return md5

        hu_lbd = self.env.ssh_by_name(self.name).run(
            'python -c "from fuel_agent.utils import hardware_utils as hu;'
            'import json; print json.dumps(hu.list_block_devices())"',
            command_timeout=tu.SSH_COMMAND_TIMEOUT)
        mock_lbd.return_value = json.loads(hu_lbd)
        #TODO(agordeev): replace with prebuild `configdrive` artifact
        self.mgr.do_parsing()
        self.mgr.do_configdrive()
        cd_size = os.path.getsize(CONFIG_DRIVE_PATH)
        cd_md5 = _get_md5sum(CONFIG_DRIVE_PATH)
        #NOTE(agordeev): assuming that configdrive was added lastly to images
        fs_type = self.env.ssh_by_name(self.name).run(
            'blkid -o value -s TYPE %s' % CONFIG_DRIVE_PATH)
        self.assertEqual('iso9660', fs_type)
        label_output = self.env.ssh_by_name(self.name).run(
            'blkid -o value -s LABEL %s' % CONFIG_DRIVE_PATH)
        self.assertEqual('cidata', label_output)
        #TODO(agordeev): add test which checks deployed configdrive image
        actual_md5 = _get_md5sum(CONFIG_DRIVE_PATH, size=cd_size)
        self.assertEqual(cd_md5, actual_md5)
        ud_output_path = os.path.join(TMP_PATH, 'user-data')
        md_output_path = os.path.join(TMP_PATH, 'meta-data')
        # create mount point for checking the configdrive's content
        self.env.ssh_by_name(self.name).run('mkdir - p /tmp/cfgdrv')
        self.env.ssh_by_name(self.name).run(
            'mount -o loop %s /tmp/cfgdrv' % CONFIG_DRIVE_PATH)

        #NOTE(agordeev): mime boundary should be the same in both files,
        #                since boundary is always randomly generated,
        #                thus magic prevents from checksum differencies
        expected_boundary = None
        with open(ud_output_path) as f:
            expected_boundary = f.read().split('\n')[0].split('"')[1]
        actual_boundary = self.env.ssh_by_name(self.name).run(
            'head -n1 %s' % ud_output_path).split('"')[1]
        md5sum_userdata_output = self.env.ssh_by_name(self.name).run(
            'sed -e s/%s/%s/ %s | md5sum' % (actual_boundary,
                                             expected_boundary,
                                             '/tmp/cfgdrv/user-data'))

        md5sum_metadata_output = self.env.ssh_by_name(self.name).run(
            'md5sum /tmp/cfgdrv/meta-data')
        actual_md5_userdata = md5sum_userdata_output.split()[0]
        actual_md5_metadata = md5sum_metadata_output.split()[0]
        expected_md5_userdata = _get_md5sum(ud_output_path)
        expected_md5_metadata = _get_md5sum(md_output_path)
        self.assertEqual(expected_md5_userdata, actual_md5_userdata)
        self.assertEqual(expected_md5_metadata, actual_md5_metadata)
