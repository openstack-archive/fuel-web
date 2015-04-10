#!/usr/bin/env python
#    Copyright 2015 Mirantis, Inc.
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
import unittest2

from fuel_package_updates.main import check_options


@mock.patch('fuel_package_updates.utils.exit_with_error',
            side_effect=SystemExit)
class TestCheckOptions(unittest2.TestCase):

    def test_list_supported_distors(self, mexit_with_error):
        options = mock.Mock(list_distros=True, verbose=True)
        with self.assertRaises(SystemExit):
            check_options(options)

        self.assertFalse(mexit_with_error.called)

    def test_not_correct_url(self, mexit_with_error):
        url = 'mirror.fuel-infra.org/repos/patching-test/ubuntu/'
        options = mock.Mock(distro='ubuntu', release='2014.2-6.1', url=url,
                            verbose=True, list_distros=False)

        with self.assertRaises(SystemExit):
            check_options(options)

        self.assertTrue(mexit_with_error.called)
        self.assertIn(url, str(mexit_with_error.call_args))
