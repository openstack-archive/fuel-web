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


class AddVersionsYaml(PreUpgradeHookBase):
    """Openstack Patching was introduced in Fuel 5.1, so we need to install
    centos-versions.yaml and ubuntu-versions.yaml for Fuel 5.0 in order to
    make possible rollback process (we need to call yum with spec version).
    """

    #: this hook required only for openstack engine
    enable_for_engines = [OpenStackUpgrader]

    #: versions files
    versions_yaml = (
        os.path.join('config', '5.0', 'centos-versions.yaml'),
        os.path.join('config', '5.0', 'ubuntu-versions.yaml'),
    )

    #: destination folder
    destination = os.path.join('/etc', 'puppet', 'manifests')

    def check_if_required(self):
        """Let's assume that we always require that hack in case
        `/etc/puppet/manifests` missed centos-versions.yaml.
        """
        return not os.path.exists(
            os.path.join(self.destination, 'centos-versions.yaml'))

    def run(self):
        """Install missed centos-versions.yaml and ubuntu-versions.yaml
        in `/etc/puppet/manifests`.
        """
        for version_yaml in self.versions_yaml:
            copy(os.path.join(self.config.update_path, version_yaml),
                 self.destination,
                 overwrite=False)
