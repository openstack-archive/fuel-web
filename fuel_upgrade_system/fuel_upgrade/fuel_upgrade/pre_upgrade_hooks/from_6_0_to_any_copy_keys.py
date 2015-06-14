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
import os

from fuel_upgrade.engines.docker_engine import DockerUpgrader
from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase

from fuel_upgrade import errors
from fuel_upgrade import utils

logger = logging.getLogger(__name__)


class MoveKeysHook(PreUpgradeHookBase):
    """Move keys from astute container to new path
    mounted in all containers.

    In 6.1 we move generating keys for granular deployment
    to tasks and now keys are in the directory mounted in
    all containers so we need to move old keys to new dir
    to have all keys in one place.
    """

    # this hook is required only for docker upgrade engine
    enable_for_engines = [DockerUpgrader]

    # src keys where we keep keys for fuel <6.1
    src_path = '/var/lib/astute/'
    # new keys destination
    dst_path = '/var/lib/fuel/keys/'

    def check_if_required(self):
        """The hack is required if we're going to upgrade from version < 6.1.
        """
        return utils.compare_version(self.config.from_version, '6.1') > 0

    def run(self):
        """Move files to new directory
        """
        if not utils.file_exists(self.dst_path):
            os.makedirs(self.dst_path)

        container_name = '{0}{1}-astute'.format(
            self.config.container_prefix, self.config.from_version)
        try:
            utils.exec_cmd('docker cp {0}:{1} {2}'.format(
                container_name,
                self.src_path,
                self.dst_path))
            # we need move and remove folder, because docker copy also folder
            # not only content
            utils.exec_cmd('mv {0}astute/* {0}'.format(self.dst_path))
            utils.exec_cmd('rm -r {0}astute/'.format(self.dst_path))
        except errors.ExecutedErrorNonZeroExitCode as exc:
                # Error means that user didn't run deployment on his
                # env, because this directory is created only then
                logger.warning(
                    'Cannot copy astute keys %s',
                    exc)
