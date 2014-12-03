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

from copy import deepcopy

from fuel_upgrade.config import read_yaml_config
from fuel_upgrade import utils

from fuel_upgrade.engines.host_system import HostSystemUpgrader
from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase

logger = logging.getLogger(__name__)


class AddMonitordKeystoneCredentialsHook(PreUpgradeHookBase):
    """Monitoring service Keystone credentials.
    """

    #: This hook required only for docker and host system engines
    enable_for_engines = [HostSystemUpgrader]

    #: New credentials
    monitord_config = {
        "user": "monitord",
        "password": utils.generate_uuid_string(),
    }

    def check_if_required(self):
        """Checks if it's required to run upgrade

        :returns: True - if it is required to run this hook
                  False - if it is not required to run this hook
        """
        is_required = not all(key in self.config.astute.get('monitord', {})
                              for key in self.monitord_config.keys())

        return is_required

    def run(self):
        """Adds default credentials to config file
        """
        # NOTE(ikalnitsky): we need to re-read astute.yaml in order protect
        # us from loosing some useful injection of another hook
        astute_config = read_yaml_config(self.config.current_fuel_astute_path)

        new_keystone_config = deepcopy(self.monitord_config)
        curent_keystone_config = deepcopy(astute_config.get('monitord', {}))
        new_keystone_config.update(curent_keystone_config)

        astute_config['monitord'] = new_keystone_config

        # NOTE(eli): Just save file for backup in case
        # if user wants to restore it manually
        utils.copy_file(
            self.config.current_fuel_astute_path,
            '{0}_{1}'.format(self.config.current_fuel_astute_path,
                             self.config.from_version),
            overwrite=False)

        utils.save_as_yaml(self.config.current_fuel_astute_path, astute_config)
