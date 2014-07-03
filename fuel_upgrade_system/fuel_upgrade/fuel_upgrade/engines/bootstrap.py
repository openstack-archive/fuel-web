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

import logging
import os

import six

from fuel_upgrade.engines.base import UpgradeEngine
from fuel_upgrade import utils


logger = logging.getLogger(__name__)


class BootstrapUpgrader(UpgradeEngine):
    """Bootstrap Upgrader.
    """

    #: a list of bootstrap files
    bootstraps = (
        'initramfs.img',
        'linux',
    )

    def __init__(self, *args, **kwargs):
        super(BootstrapUpgrader, self).__init__(*args, **kwargs)

        #: an old fuel version
        self._old_version = self.config.current_version

        #: bootstrap file -> various paths map
        #:
        #: useful dict with information about src/dst/backup paths
        #: for files.
        self._bootstraps = {}

        for file_ in self.bootstraps:
            self._bootstraps[file_] = {
                'src': os.path.join(self.config.bootstrap['src'], file_),
                'dst': os.path.join(self.config.bootstrap['dst'], file_),

                'backup': os.path.join(
                    self.config.bootstrap['dst'], '{0}_{1}'.format(
                        self._old_version, file_
                    )
                ),
            }

    def upgrade(self):
        logger.info('bootstrap upgrader: starting...')

        self.backup()

        for _, paths in six.iteritems(self._bootstraps):
            utils.copy(paths['src'], paths['dst'])

        logger.info('bootstrap upgrader: done')

    def rollback(self):
        logger.info('Rollbacking bootstrap files...')

        for _, paths in six.iteritems(self._bootstraps):
            utils.remove_if_exists(paths['dst'])
            utils.copy(paths['backup'], paths['dst'])

    def backup(self):
        logger.info('Backuping bootstrap files...')

        for _, paths in six.iteritems(self._bootstraps):
            utils.rename(paths['dst'], paths['backup'])

    @property
    def required_free_space(self):
        """Required free space to run upgrade

        Please keep in mind that we need to calculate old bootstraps size
        too because we make a backup.

        :returns: dict where key is path to directory
                  and value is required free space
        """
        size = 0
        for _, paths in six.iteritems(self._bootstraps):
            size += utils.files_size([
                paths['src'],   # source
                paths['dst'],   # backup
            ])

        return {
            self.config.bootstrap['dst']: size
        }
