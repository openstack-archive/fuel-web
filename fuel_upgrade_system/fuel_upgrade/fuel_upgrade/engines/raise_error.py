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

from fuel_upgrade.engines.base import UpgradeEngine
from fuel_upgrade import errors


class RaiseErrorUpgrader(UpgradeEngine):
    """The test upgrader intended to use in system tests.

    In order to test the rollback feature we used to inject raising error
    code in one of our upgraders in-place::

        self.fuel_web.modify_python_file(self.env.get_admin_remote(),
                                        "61i \ \ \ \ \ \ \ \ raise errors."
                                        "ExecutedErrorNonZeroExitCode('{0}')"
                                        .format('Some bad error'),
                                        '/var/upgrade/site-packages/'
                                        'fuel_upgrade/engines/'
                                        'openstack.py')

    It's a bad design decision which leads to time-to-time falls in tests due
    to changes in the upgrader's code. So the class is going to solve this
    issue by providing a special upgrader which will always fail.
    """

    error_message = 'Something Goes Wrong'

    def upgrade(self):
        raise errors.FuelUpgradeException(self.error_message)

    def rollback(self):
        return NotImplemented

    @property
    def required_free_space(self):
        return {}
