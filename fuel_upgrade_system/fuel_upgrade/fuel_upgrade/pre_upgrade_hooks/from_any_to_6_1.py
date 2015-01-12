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

from fuel_upgrade.engines.host_system import HostSystemUpgrader
from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase
from fuel_upgrade.utils import exec_cmd


logger = logging.getLogger(__name__)


class StopDockerService(PreUpgradeHookBase):
    """Stops a Docker service safely.

    Before Fuel 6.1, we had an issue with Docker and device-mapper. The issue
    was that we can't just make `service docker stop`, since it keeps stale
    mounted resource.

    In order to update Docker, we need to do it safely. That means we need
    perform:

    * docker stop $(docker ps -q -a)
    * umount -l $(grep docker /proc/mounts | awk '{print $2}' | sort -r)
    * service docker stop

    """
    # this hook required only for updating docker package
    enable_for_engines = [HostSystemUpgrader]

    # commands to stop docker safely. they are simple shell commands,
    # since i don't think it's a good idea to spend much time on this
    # hack trying to imlement it using supervisor/docker clients.
    commands = [
        'supervisorctl stop all',
        'docker stop $(docker ps -q -a)',
        'mount -l $(grep docker /proc/mounts | awk "{print $2}" | sort -r)',
        'service docker stop', ]

    def check_if_required(self):
        return self.config.to_version == '6.1'

    def run(self):
        for command in self.commands:
            exec_cmd(command)
