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

from fuel_upgrade.engines.host_system import HostSystemUpgrader
from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase

from fuel_upgrade.utils import safe_exec_cmd


class KillSupervisordHook(PreUpgradeHookBase):
    """Kill supervisord process.

    In Fuel 5.0 we have broken supervisor configs, so the

        $ service supervisor stop

    leads to timeout with exit code `1` which breaks `puppet apply`
    and whole upgrade process.

    Related bug: https://bugs.launchpad.net/fuel/+bug/1350764
    """

    #: this hook is required only for host-system engine
    enable_for_engines = [HostSystemUpgrader]

    #: commands to kill supervisord
    commands = [
        'kill -9 `cat /var/run/supervisord.pid`',
        'rm -f /var/run/supervisord.pid',
        'pkill -f "docker.*D.*attach.*fuel-core"',
        'pkill -f "dockerctl.*start.*attach"']

    def check_if_required(self):
        """The hack is required if we're going to upgrade from 5.0 to any.
        """
        return self.config.from_version in ('5.0', )

    def run(self):
        for command in self.commands:
            safe_exec_cmd(command)
