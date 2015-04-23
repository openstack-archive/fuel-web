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

import functools
import logging
import os
import re

from io import open

from fuel_upgrade.engines.docker_engine import DockerUpgrader
from fuel_upgrade.engines.host_system import HostSystemUpgrader
from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase

from fuel_upgrade import utils


logger = logging.getLogger(__name__)


class SetFixedVersionInSupervisor(PreUpgradeHookBase):
    """Set fixed version in containers' supervisor configs.

    Currently, containers' supervisor configs don't have the Fuel version
    in the command line. It means that when supervisor tries to start a
    container its version retrieved on fly from the '/etc/fuel/version.yaml'.
    Since Fuel 6.1, the '/etc/fuel/version.yaml` has to be new, because
    otherwise the 'host-upgrade.pp' will use incorrect current version.
    Unfortunately, if '/etc/fuel/version.yaml' is new and the puppet
    upgrades Docker package, the Docker containers will be stopped and
    they won't up again because 'detecting container version on fly' will
    give us wrong result (e.g. 6.1 instead of 6.0). So, the only thing
    we can do is to set fixed container version in supervisor's configs,
    so it won't rely on current state of '/etc/fuel/version.yaml'.
    """

    #: this hook is required only for docker upgrade engine
    enable_for_engines = [HostSystemUpgrader, DockerUpgrader]

    #: a list of containers for which we have to change supervisor configs.
    #: please note, it's better to have an explicit list, because user
    #: may have custom supervisor confs and we don't want to touch them.
    _containers = [
        'astute',
        'cobbler',
        'keystone',
        'mcollective',
        'nailgun',
        'nginx',
        'ostf',
        'postgres',
        'rabbitmq',
        'rsync',
        'rsyslog',
    ]

    def __init__(self, *args, **kwargs):
        super(SetFixedVersionInSupervisor, self).__init__(*args, **kwargs)

        #: a function that recieves input text, replace command string
        #: and returns result
        self._replace = functools.partial(
            re.compile(r'command=dockerctl start (\w+) --attach').sub,
            r'command=docker start -a fuel-core-{version}-\1'.format(
                version=self.config.from_version))

    def _set_version_in(self, confname):
        with open(confname, 'rt', encoding='utf-8') as f:
            data = self._replace(f.read())

        with open(confname, 'wt', encoding='utf-8') as f:
            f.write(data)

    def check_if_required(self):
        # should be applied if from_version < 6.1
        return utils.compare_version(self.config.from_version, '6.1') > 0

    def run(self):
        for container in self._containers:
            confname = '/etc/supervisord.d/{version}/{container}.conf'.format(
                version=self.config.from_version,
                container=container)

            if os.path.exists(confname):
                self._set_version_in(confname)
            else:
                logger.info('Could not find supervisor conf: "%s"', confname)

        # apply updated configurations without actual restart
        utils.safe_exec_cmd('supervisorctl update')
