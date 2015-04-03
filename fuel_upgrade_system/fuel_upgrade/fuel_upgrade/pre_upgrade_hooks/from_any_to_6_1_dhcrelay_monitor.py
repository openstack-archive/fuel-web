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

import os
import stat

from fuel_upgrade.engines.docker_engine import DockerUpgrader
from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase

from fuel_upgrade import utils


class FixDhcrelayMonitor(PreUpgradeHookBase):
    """Fix dhcrelay_monitor wrapper for dhcrelay

    Since Fuel 6.1 we're going to use docker with host networking, so
    we don't require dhcrelay anymore. Still, if something goes wrong
    and rollback was performed, we need to launch dhcrelay again
    (because it was shutdown by host manifests). In order to do it
    properly, we need to get cobbler container's ip address, but
    we don't have such hook in dockerctl anymore.

    This hoos is intended to inject code with "retrieve ip address"
    to dhcrelay_monitor directly.
    """

    enable_for_engines = [DockerUpgrader]

    _save_from = os.path.join(
        os.path.dirname(__file__), '..', 'templates', 'dhcrelay_monitor')

    _save_to = '/usr/local/bin/dhcrelay_monitor'

    def check_if_required(self):
        # not required if fuel is already higher than 6.1
        if utils.compare_version('6.1', self.config.from_version) >= 0:
            return False
        return True

    def run(self):
        utils.copy(self._save_from, self._save_to, overwrite=True)

        # make sure that the file is still executable
        st = os.stat(self._save_to)
        os.chmod(self._save_to, st.st_mode | stat.S_IEXEC)
