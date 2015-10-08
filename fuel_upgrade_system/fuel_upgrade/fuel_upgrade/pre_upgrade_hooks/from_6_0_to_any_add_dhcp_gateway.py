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

from fuel_upgrade.engines.docker_engine import DockerUpgrader
from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase

logger = logging.getLogger(__name__)


class AddDhcpGateway(PreUpgradeHookBase):
    """Inject dhcp_gateway setting into astute.yaml

    Since Fuel 6.1 we have a new field in astute.yaml - "dhcp_gateway".
    It's mandatory to have that field because it will be used by native
    provisioning as gateway. Without it, we won't be able to use native
    provisioning with external repos.
    """

    #: this hook required only for docker engine
    enable_for_engines = [DockerUpgrader]

    #: network settings to be injected into astute.yaml
    _admin_network = {
        'ADMIN_NETWORK': {
            'dhcp_gateway': None,
        }
    }

    def __init__(self, *args, **kwargs):
        super(AddDhcpGateway, self).__init__(*args, **kwargs)

        gw = self.config.master_ip
        self._admin_network['ADMIN_NETWORK']['dhcp_gateway'] = gw

    def check_if_required(self):
        inject = set(self._admin_network['ADMIN_NETWORK'])
        exists = set(self.config.astute.get('ADMIN_NETWORK', {}))
        return inject - exists

    def run(self):
        """Adds dhcp gateway to astute.yaml"""
        self.update_astute_config(defaults=self._admin_network)
