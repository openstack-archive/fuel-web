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

import json
import re

from fuel_upgrade.engines.host_system import HostSystemUpgrader
from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase

from fuel_upgrade.utils import compare_version
from fuel_upgrade.utils import exec_cmd_iterator
from fuel_upgrade.utils import safe_exec_cmd


class RecreateNailgunInPriveleged(PreUpgradeHookBase):
    """Recreate Nailgun container in priveleged mode.

    Since Docker 0.11 all access to both /proc and /sys are restricted
    and requires a privileged mode. Unfortunately, it affects us because
    Nailgun container fails to execute the following line:

        sysctl -w net.core.somaxconn=4096

    So we have to recreate Nailgun container in privileged mode in order
    to be compatible with both old and new Docker.

    https://github.com/docker/docker/issues/5703
    """

    #: this hook required only for updating docker package
    enable_for_engines = [HostSystemUpgrader]

    #: regexp that extracts version from 'docker --version' output
    _docker_version = re.compile('Docker version ([0-9.]+)')

    def __init__(self, *args, **kwargs):
        super(RecreateNailgunInPriveleged, self).__init__(*args, **kwargs)

        from_version = self.config.from_version
        self._container = 'fuel-core-{0}-nailgun'.format(from_version)
        self._image = 'fuel/nailgun_{0}'.format(from_version)

    def check_if_required(self):
        # not required if fuel is already higher than 6.1
        if compare_version('6.1', self.config.from_version) > 0:
            return False

        # not required if container is in privileged mode already
        container = json.loads('\n'.join(
            exec_cmd_iterator('docker inspect {0}'.format(self._container))))
        if container.get('HostConfig', {}).get('Privileged'):
            return False

        # not required if docker is already higher than 0.11
        output = '\n'.join(exec_cmd_iterator('docker --version'))
        match = self._docker_version.match(output)
        if match:
            version = match.group(1)
            return compare_version('0.11.0', version) < 0
        return False

    def _stop_container(self):
        safe_exec_cmd('docker stop {0}'.format(self._container))

    def _destroy_container(self):
        safe_exec_cmd('docker rm -f {0}'.format(self._container))

    def _create_container(self):
        command = ' '.join([
            'docker run -d -t --privileged',
            '-p {BIND_ADMIN}:8001:8001',
            '-p {BIND_LOCAL}:8001:8001',
            '-v /etc/nailgun',
            '-v /var/log/docker-logs:/var/log',
            '-v /var/www/nailgun:/var/www/nailgun:rw',
            '-v /etc/yum.repos.d:/etc/yum.repos.d:rw',
            '-v /etc/fuel:/etc/fuel:ro',
            '-v /root/.ssh:/root/.ssh:ro',
            '--name={CONTAINER}',
            '{IMAGE}'])

        command = command.format(
            BIND_ADMIN=self.config.master_ip,
            BIND_LOCAL='127.0.0.1',
            CONTAINER=self._container,
            IMAGE=self._image)

        safe_exec_cmd(command)

    def run(self):
        self._stop_container()
        self._destroy_container()
        self._create_container()
