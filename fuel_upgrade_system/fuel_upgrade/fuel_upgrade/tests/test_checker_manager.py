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

import mock

from fuel_upgrade.checker_manager import CheckerManager
from fuel_upgrade.tests.base import BaseTestCase


class TestCheckerManager(BaseTestCase):

    def setUp(self):
        self.config = self.fake_config

        class Upgrader1(mock.MagicMock):
            pass

        class Upgrader2(mock.MagicMock):
            pass

        class Upgrader3(mock.MagicMock):
            pass

        class Checker1(mock.MagicMock):
            pass

        class Checker2(mock.MagicMock):
            pass

        class Checker3(mock.MagicMock):
            pass

        self.checker_classes = [Checker1, Checker2, Checker3]

        self.checker_mapping = {
            Upgrader1: [self.checker_classes[0], self.checker_classes[1]],
            Upgrader2: [self.checker_classes[0], self.checker_classes[2]],
            Upgrader3: []}

        self.upgraders = [Upgrader1(), Upgrader2(), Upgrader3()]

        self.required_free_space_mocks = []
        # Mock property
        for upgarde in self.upgraders:
            required_free_space_mock = mock.PropertyMock()
            type(upgarde).required_free_space = required_free_space_mock
            self.required_free_space_mocks.append(required_free_space_mock)

        self.checker_manager = CheckerManager(self.upgraders, self.config)

    def test_init(self):
        self.checker_manager.check()
        for required_free_space_mock in self.required_free_space_mocks:
            self.called_once(required_free_space_mock)

    def test_check(self):
        checkers = [c() for c in self.checker_classes]
        with mock.patch('fuel_upgrade.checker_manager.'
                        'CheckerManager._checkers',
                        return_value=checkers):
            self.checker_manager.check()

            for checker in checkers:
                self.called_once(checker.check)

    def test_checkers(self):
        with mock.patch(
                'fuel_upgrade.checker_manager.'
                'CheckerManager.CHECKERS_MAPPING',
                new_callable=mock.PropertyMock(
                    return_value=self.checker_mapping)):
            checekrs = self.checker_manager._checkers()
            self.assertEqual(len(checekrs), 3)
