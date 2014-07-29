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

from fuel_upgrade import utils

logger = logging.getLogger(__name__)


class VersionFile(object):
    """Fuel version file manager

    :param config: :class:`Config` object
    """

    def __init__(self, config):
        #: src path to new version yaml file
        self.src_new_version_file = config.new_upgrade_version_path

        #: dst path to new version yaml file
        self.dst_new_version_file = config.new_version_path

        #: path to current version file
        self.current_version_file = config.current_fuel_version_path

        #: path to previous version file
        self.previous_version_file = config.previous_version_path

        #: path to saved version yaml
        self.store_version_file = config.from_version_path

    def save_current(self):
        """Save current version in working
        directory if it was not saved during
        previous run.

        This action is important in case
        when upgrade script was interrupted
        after symlinking of version.yaml file.
        """
        utils.create_dir_if_not_exists(os.path.dirname(
            self.store_version_file))
        utils.copy_if_does_not_exist(
            self.current_version_file,
            self.store_version_file)

    def switch_to_new(self):
        """Switche version file to new version

        * creates new version yaml file
        * and creates symlink to /etc/fuel/version.yaml
        """
        logger.info(u'Switch version file to new version')

        utils.create_dir_if_not_exists(os.path.dirname(
            self.dst_new_version_file))

        utils.copy(
            self.src_new_version_file,
            self.dst_new_version_file)

        utils.symlink(
            self.dst_new_version_file,
            self.current_version_file)

    def switch_to_previous(self):
        """Switch version file symlink to previous version
        """
        logger.info(u'Switch current version file to previous version')
        utils.symlink(self.previous_version_file, self.current_version_file)
