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


from oslotest import base as test_base

from fuel_agent import errors
from fuel_agent.objects import configdrive


class TestConfigDriveScheme(test_base.BaseTestCase):

    def setUp(self):
        super(TestConfigDriveScheme, self).setUp()
        self.cd_scheme = configdrive.ConfigDriveScheme()

    def test_template_name(self):
        actual = self.cd_scheme.template_name('what')
        expected = '%s_%s.jinja2' % ('what', self.cd_scheme._profile)
        self.assertEqual(expected, actual)

    def test_template_data_no_common(self):
        self.assertRaises(errors.WrongConfigDriveDataError,
                          self.cd_scheme.template_data)

    def test_template_data_ok(self):
        cd_common = configdrive.ConfigDriveCommon(
            'ssh_auth_key', 'hostname', 'fqdn', 'name_servers',
            'search_domain', 'master_ip', 'master_url', 'udevrules',
            'admin_mac', 'admin_ip', 'admin_mask', 'admin_iface_name',
            'timezone')
        cd_puppet = configdrive.ConfigDrivePuppet('master')
        cd_mcollective = configdrive.ConfigDriveMcollective(
            'pskey', 'vhost', 'host', 'user', 'password', 'connector')
        self.cd_scheme.common = cd_common
        self.cd_scheme.puppet = cd_puppet
        self.cd_scheme.mcollective = cd_mcollective
        template_data = self.cd_scheme.template_data()
        self.assertEqual(cd_common, template_data['common'])
        self.assertEqual(cd_puppet, template_data['puppet'])
        self.assertEqual(cd_mcollective, template_data['mcollective'])
