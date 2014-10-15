#    Copyright 2014 Mirantis, Inc.
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

import mock
import yaml

from tasklib import config
from tasklib.tests import base


@mock.patch('tasklib.task.os.path.exists')
class TestConfig(base.BaseUnitTest):

    def test_default_config_when_no_file_exists(self, mexists):
        mexists.return_value = False
        conf = config.Config(config_file='/etc/tasklib/test.yaml')
        self.assertEqual(conf.default_config, conf.config)

    def test_default_when_no_file_provided(self, mexists):
        conf = config.Config()
        self.assertEqual(conf.default_config, conf.config)

    def test_non_default_config_from_valid_yaml(self, mexists):
        mexists.return_value = True
        provided = {'library_dir': '/var/run/tasklib',
                    'puppet_manifest': 'init.pp'}
        mopen = mock.mock_open(read_data=yaml.dump(provided))
        with mock.patch('tasklib.config.open', mopen, create=True):
            conf = config.Config(config_file='/etc/tasklib/test.yaml')
            self.assertNotEqual(
                conf.config['library_dir'], conf.default_config['library_dir'])
            self.assertEqual(
                conf.config['library_dir'], provided['library_dir'])
            self.assertNotEqual(
                conf.config['puppet_manifest'],
                conf.default_config['puppet_manifest'])
            self.assertEqual(
                conf.config['puppet_manifest'], provided['puppet_manifest'])
