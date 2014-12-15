# -*- coding: utf-8 -*-

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

from fuel_upgrade.engines.raise_error import RaiseErrorUpgrader
from fuel_upgrade import errors
from fuel_upgrade.tests.base import BaseTestCase


class TestRaiseErrorUpgrader(BaseTestCase):

    def setUp(self):
        self.upgrader = RaiseErrorUpgrader(self.fake_config)

    def test_upgrade_raise_error(self):
        self.assertRaisesRegexp(
            errors.FuelUpgradeException,
            RaiseErrorUpgrader.error_message,
            self.upgrader.upgrade)
