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

from fuel_upgrade.engines.targetimages import TargetimagesUpgrader
from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase

from fuel_upgrade import utils


class CreateTargetimages(PreUpgradeHookBase):
    """Create {www-root}/{current-version}_targetimages directory and symlink
    {www-root}/targetimages -> {www-root}/{current-version}_targetimages.

    {www-root}/targetimages directory is necessary for
    image based provisioning. It does not exist at 5.1.
    """
    #: this hook is required only for targetimages engine
    enable_for_engines = [TargetimagesUpgrader]

    versioned_targetimages = '/var/www/nailgun/5.1_targetimages'
    link_targetimages = '/var/www/nailgun/targetimages'

    def check_if_required(self):
        """The hack is required if we're going to upgrade from 5.1.
        """
        return self.config.from_version in ('5.1', '5.1.1')

    def run(self):
        """Create versioned directory and symlink
        """
        utils.create_dir_if_not_exists(self.versioned_targetimages)
        utils.symlink(self.versioned_targetimages, self.link_targetimages)
