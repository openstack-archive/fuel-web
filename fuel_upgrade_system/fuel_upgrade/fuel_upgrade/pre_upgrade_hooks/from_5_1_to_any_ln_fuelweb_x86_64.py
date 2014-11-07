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

from fuel_upgrade import utils

from fuel_upgrade.engines.docker_engine import DockerUpgrader
from fuel_upgrade.engines.host_system import HostSystemUpgrader
from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase

logger = logging.getLogger(__name__)


class AddFuelwebX8664LinkForUbuntu(PreUpgradeHookBase):
    """Add link for repo/ubuntu/x86_64 -> repo/ubuntu/fuelweb/x86_64

    In Fuel 6.0 we have dropped legacy 'fuelweb' folder from the repos,
    but we can't do this for old (already installed) repos. Unfortunately,
    this leads us to the issue when cobbler using new puppets/configs tries
    to load Ubuntu installer from repo/ubuntu/x86_64 when it's located
    in repo/ubuntu/fuelweb/x86_64.

    Generally, it's another issue that we use old installers for both
    centos/ubuntu, but it's not fixed yet, so we need to introduce
    such hack.
    """

    #: this hook required only for docker and host system engines
    enable_for_engines = [DockerUpgrader, HostSystemUpgrader]

    #: link to old ubuntu x86_64
    ubuntu_x86_64_old = '/var/www/nailgun/ubuntu/fuelweb/x86_64'
    ubuntu_x86_64_new = '/var/www/nailgun/ubuntu/x86_64'

    def check_if_required(self):
        """Checks if it's required to run upgrade

        :returns: True - if it is required to run this hook
                  False - if it is not required to run this hook
        """
        return all([
            utils.file_exists(self.ubuntu_x86_64_old),
            not utils.file_exists(self.ubuntu_x86_64_new)])

    def run(self):
        """Add link for repo/ubuntu/x86_64 -> repo/ubuntu/fuelweb/x86_64
        """
        utils.symlink(self.ubuntu_x86_64_old, self.ubuntu_x86_64_new)
