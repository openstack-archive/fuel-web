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

from fuel_upgrade.engines.docker_engine import DockerUpgrader
from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase

from fuel_upgrade.utils import copy_file
from fuel_upgrade.utils import remove
from fuel_upgrade.utils import safe_exec_cmd


class FixDhcrelayConf(PreUpgradeHookBase):
    """Fix supervisor's dhcrelay.conf

    Since Fuel 6.1 we're going to use docker with host networking, so
    we don't require dhcrelay anymore. Still, if something goes wrong
    and rollback was performed, we need to launch dhcrelay again
    (because it was shutdown by host manifests).

    In order to run it when we want to use old containers, we need to:

    * add dhcrelay.conf to versioned supervisor folder
    * remove dhcrelay.conf from global supervisor scope
    """

    #: this hook required only for --net=host containers
    enable_for_engines = [DockerUpgrader]

    #: copy from
    _save_from = os.path.join('/etc', 'supervisord.d', 'dhcrelay.conf')

    #: save path
    _save_to = os.path.join(
        '/etc', 'supervisord.d', '{version}', 'dhcrelay.conf')

    def __init__(self, *args, **kwargs):
        super(FixDhcrelayConf, self).__init__(*args, **kwargs)

        self._save_to = self._save_to.format(version=self.config.from_version)

    def check_if_required(self):
        if os.path.exists(self._save_from) and \
                not os.path.exists(self._save_to):
            return True
        return False

    def run(self):
        # save dhcrelay.conf to versioned folder
        copy_file(self._save_from, self._save_to)
        # remove dhcrelay.conf from global supervisor scope
        remove(self._save_from)
        # stop dhcrelay in supervisord, otherwise it will be re-ran
        # automatically
        safe_exec_cmd('supervisorctl stop dhcrelay_monitor')
