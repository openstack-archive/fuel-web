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

from fuel_upgrade.engines.docker_engine import DockerUpgrader
from fuel_upgrade.engines.host_system import HostSystemUpgrader
from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase

logger = logging.getLogger(__name__)


class SyncDnsHook(PreUpgradeHookBase):
    """Bug `Fix dns domain and search settings on Fuel Master`
    was introduced in 5.1 release [1].

    In this feature fuelmenu parses existing DNS
    settings and applies them as a default instead
    of its own in /etc/fuel/astute.yaml.

    Before upgrade for this feature, we need to
    correct /etc/fuel/astute.yaml to match
    /etc/resolv.conf.

    [1] Fix dns domain and search settings on Fuel Master
    """

    #: This hook required only for docker and host system engines
    enable_for_engines = [DockerUpgrader, HostSystemUpgrader]

    def check_if_required(self):
        """Checks if it's required to run upgrade

        :returns: True - if it is required to run this hook
                  False - if it is not required to run this hook
        """
        astute_domain = self.config.astute['DNS_DOMAIN']
        astute_search = self.config.astute['DNS_SEARCH']
        hostname, sep, realdomain = os.uname()[1].partition('.')

        is_required = not all([astute_domain == realdomain,
                              realdomain in astute_search])
        return is_required

    def run(self):
        """Replaces config file with current DNS domain
        """
        hostname, sep, realdomain = os.uname()[1].partition('.')
        self.update_astute_config(overwrites={
            'DNS_DOMAIN': realdomain,
            'DNS_SEARCH': realdomain,
        })
