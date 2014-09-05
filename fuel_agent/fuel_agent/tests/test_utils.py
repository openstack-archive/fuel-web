# Copyright 2011 Justin Santa Barbara
# Copyright 2012 Hewlett-Packard Development Company, L.P.
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

import testtools

import mock
import stevedore

from fuel_agent import errors
from fuel_agent.utils import utils


class ExecuteTestCase(testtools.TestCase):
    """This class is partly based on the same class in openstack/ironic."""

    def setUp(self):
        super(ExecuteTestCase, self).setUp()
        fake_driver = stevedore.extension.Extension('fake_driver', None, None,
                                                    'fake_obj')
        self.drv_manager = stevedore.driver.DriverManager.make_test_instance(
            fake_driver)

    def test_parse_unit(self):
        self.assertEqual(utils.parse_unit('1.00m', 'm', ceil=True), 1)
        self.assertEqual(utils.parse_unit('1.00m', 'm', ceil=False), 1)
        self.assertEqual(utils.parse_unit('1.49m', 'm', ceil=True), 2)
        self.assertEqual(utils.parse_unit('1.49m', 'm', ceil=False), 1)
        self.assertEqual(utils.parse_unit('1.51m', 'm', ceil=True), 2)
        self.assertEqual(utils.parse_unit('1.51m', 'm', ceil=False), 1)
        self.assertRaises(ValueError, utils.parse_unit, '1.00m', 'MiB')
        self.assertRaises(ValueError, utils.parse_unit, '', 'MiB')

    def test_B2MiB(self):
        self.assertEqual(utils.B2MiB(1048575, ceil=False), 0)
        self.assertEqual(utils.B2MiB(1048576, ceil=False), 1)
        self.assertEqual(utils.B2MiB(1048575, ceil=True), 1)
        self.assertEqual(utils.B2MiB(1048576, ceil=True), 1)
        self.assertEqual(utils.B2MiB(1048577, ceil=True), 2)

    def test_check_exit_code_boolean(self):
        utils.execute('/usr/bin/env', 'false', check_exit_code=False)
        self.assertRaises(errors.ProcessExecutionError,
                          utils.execute,
                          '/usr/bin/env', 'false', check_exit_code=True)

    @mock.patch('stevedore.driver.DriverManager')
    def test_get_driver(self, mock_drv_manager):
        mock_drv_manager.return_value = self.drv_manager
        self.assertEqual('fake_obj', utils.get_driver('fake_driver'))

    @mock.patch('jinja2.Environment')
    @mock.patch('jinja2.FileSystemLoader')
    @mock.patch('six.moves.builtins.open')
    def test_render_and_save_fail(self, mock_open, mock_j_lo, mock_j_env):
        mock_open.side_effect = Exception('foo')
        self.assertRaises(errors.TemplateWriteError, utils.render_and_save,
                          'fake_dir', 'fake_tmpl_name', 'fake_data',
                          'fake_file_name')

    @mock.patch('jinja2.Environment')
    @mock.patch('jinja2.FileSystemLoader')
    @mock.patch('six.moves.builtins.open')
    def test_render_and_save_ok(self, mock_open, mock_j_lo, mock_j_env):
        mock_render = mock.Mock()
        mock_render.render.return_value = 'fake_data'
        mock_j_env.get_template.return_value = mock_render
        utils.render_and_save('fake_dir', 'fake_tmpl_name', 'fake_data',
                              'fake_file_name')
        mock_open.assert_called_once_with('fake_file_name', 'w')
