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

import os

from fuel_upgrade.engines.openstack import OpenStackUpgrader
from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase

from fuel_upgrade.utils import copy
from fuel_upgrade.utils import file_contains_lines


class ApplyVersioncmpFix(PreUpgradeHookBase):
    """Apply versioncmp fix for yum provider in puppet manifests.

    Openstack Patching was introduced in Fuel 5.1, but we need some fixes
    in puppet manifests for both 5.0 and 5.0.1 releases in order to provide
    working rollback feature.
    """

    #: this hook required only for openstack engine
    enable_for_engines = [OpenStackUpgrader]

    #: versions files
    yum_providers = {
        '5.0': os.path.join('config', '5.0', 'yum.rb'),
        '5.0.1': os.path.join('config', '5.0.1', 'yum.rb'),
    }

    #: a path to puppets
    puppet = '/etc/puppet'

    #: a path to providers package insinde puppet modules
    destination = 'modules/package/lib/puppet/provider/package/yum.rb'

    def check_if_required(self):
        """Let's assume that we require this hack if default yum provider
        doesn't contain ``rpm_versioncmp`` function.
        """
        return not file_contains_lines(
            os.path.join(self.puppet, self.destination),
            ['rpm_versioncmp'])

    def run(self):
        """Copy new yum.rb provider for both 5.0 and 5.0.1 releases.

        There are two installation strategies based on master node state:

        * We need to install for both 5.0 and 5.0.1 puppets in case of
          upgraded state (5.0 -> 5.0.1).

        * We need to install just one file in default location in case of
          pure state (previous installation was fresh).
        """
        if not os.path.exists(os.path.join(self.puppet, '5.0.1')):
            # ok, we are in a pure state: either 5.0 or 5.0.1
            copy(
                os.path.join(
                    self.config.update_path,
                    self.yum_providers[self.config.from_version]),
                os.path.join(
                    self.puppet, self.destination),
                overwrite=True)
        else:
            # we aren't in a pure state, so we should install yum.rb for
            # both 5.0 and 5.0.1 puppets
            copy(
                os.path.join(
                    self.config.update_path,
                    self.yum_providers['5.0']),
                os.path.join(
                    self.puppet, self.destination),
                overwrite=True)

            copy(
                os.path.join(
                    self.config.update_path,
                    self.yum_providers['5.0.1']),
                os.path.join(
                    self.puppet, '5.0.1', self.destination),
                overwrite=True)
