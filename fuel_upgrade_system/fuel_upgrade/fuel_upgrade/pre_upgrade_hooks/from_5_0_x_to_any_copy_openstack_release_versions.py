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

from os.path import join

from fuel_upgrade.engines.openstack import OpenStackUpgrader
from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase

from fuel_upgrade import utils


class CopyOpenstackReleaseVersions(PreUpgradeHookBase):
    """Copy openstack release version files.

    In previous versions of fuel, openstack packages
    and manifests had the same version as the rest
    of the system, nailgun, astute.

    In 5.1 was introduced patching, as result openstack
    packages and manifests can be delivered separately.
    And this bundle have separate version.

    Release versions are stored in `/etc/fuel/release_versions/`
    directory.
    """

    #: this hook is required only for openstack engine
    enable_for_engines = [OpenStackUpgrader]

    #: path to release versions directory
    release_dir = '/etc/fuel/release_versions'

    #: version file path for 5.0
    version_path_5_0 = '/etc/fuel/5.0/version.yaml'
    dst_version_path_5_0 = join(release_dir, '2014.1-5.0.yaml')

    #: version file path for 5.0.1
    version_path_5_0_1 = '/etc/fuel/5.0.1/version.yaml'
    dst_version_path_5_0_1 = join(release_dir, '2014.1.1-5.0.1.yaml')

    def check_if_required(self):
        """The hack is required if we're going to upgrade from 5.0 or 5.0.1.
        """
        return self.config.from_version in ('5.0', '5.0.1')

    def run(self):
        """Copy version files
        """
        utils.create_dir_if_not_exists(self.release_dir)
        utils.copy_if_exists(self.version_path_5_0, self.dst_version_path_5_0)

        # NOTE(eli): in case of failed upgrade
        # from 5.0 to 5.0.1 file for 5.0.1 can
        # be there, but in fact 5.0.1 was not
        # installed
        if self.config.from_version == '5.0.1':
            utils.copy_if_exists(
                self.version_path_5_0_1,
                self.dst_version_path_5_0_1)
