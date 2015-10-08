# -*- coding: utf-8 -*-

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

import logging

from fuel_upgrade import utils

from fuel_upgrade.engines.host_system import HostSystemUpgrader
from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase

logger = logging.getLogger(__name__)


class AddMonitordKeystoneCredentialsHook(PreUpgradeHookBase):
    """Monitoring service Keystone credentials: [1].

    This patch updates the astute.yaml file adding 'monitord' user credentials.
    This user is required to create Fuel notifications when disk space on
    master node is getting low. We don't want to use the standard 'admin' user
    because when user changes password via UI it's not reflected in the
    astute.yaml file.

    [1] https://bugs.launchpad.net/fuel/+bug/1371757
    """

    # : This hook required only for docker and host system engines
    enable_for_engines = [HostSystemUpgrader]

    # : New credentials
    keystone_config = {
        'keystone': {
            "monitord_user": "monitord",
            "monitord_password": utils.generate_uuid_string(),
        }
    }

    def check_if_required(self):
        return len(
            set(self.keystone_config['keystone']).difference(
                self.config.astute.get('keystone', {})
            )
        )

    def run(self):
        """Adds default credentials to config file"""
        self.update_astute_config(defaults=self.keystone_config)
