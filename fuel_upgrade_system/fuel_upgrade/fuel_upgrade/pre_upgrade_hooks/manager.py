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

from fuel_upgrade.pre_upgrade_hooks.from_5_0_1_to_any_fix_host_system_repo \
    import FixHostSystemRepoHook
from fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_add_credentials \
    import AddCredentialsHook
from fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_fix_puppet_manifests \
    import FixPuppetManifests
from fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_sync_dns \
    import SyncDnsHook
from fuel_upgrade.pre_upgrade_hooks. \
    from_5_0_x_to_any_copy_openstack_release_versions \
    import CopyOpenstackReleaseVersions
from fuel_upgrade.pre_upgrade_hooks.from_5_1_to_any_add_keystone_credentials \
    import AddKeystoneCredentialsHook
from fuel_upgrade.pre_upgrade_hooks.from_5_1_to_any_ln_fuelweb_x86_64 \
    import AddFuelwebX8664LinkForUbuntu
from fuel_upgrade.pre_upgrade_hooks.from_6_0_to_any_add_dhcp_gateway \
    import AddDhcpGateway
from fuel_upgrade.pre_upgrade_hooks.from_6_0_to_any_add_monitord_credentials \
    import AddMonitordKeystoneCredentialsHook
from fuel_upgrade.pre_upgrade_hooks.from_6_0_to_any_copy_keys \
    import MoveKeysHook
from fuel_upgrade.pre_upgrade_hooks.from_any_to_6_1_dhcrelay_conf \
    import FixDhcrelayConf
from fuel_upgrade.pre_upgrade_hooks.from_any_to_6_1_dhcrelay_monitor \
    import FixDhcrelayMonitor
from fuel_upgrade.pre_upgrade_hooks.from_any_to_6_1_fix_version_in_supervisor \
    import SetFixedVersionInSupervisor
from fuel_upgrade.pre_upgrade_hooks.from_any_to_6_1_recreate_containers \
    import RecreateNailgunInPriveleged

logger = logging.getLogger(__name__)


class PreUpgradeHookManager(object):
    """Runs hooks before upgrade if required

    :param list upgraders: list of :class:`BaseUpgrader` implementations
    :param config: :class:`Config` object
    """

    #: List of hook clases
    hook_list = [
        AddCredentialsHook,
        AddDhcpGateway,
        AddFuelwebX8664LinkForUbuntu,
        AddKeystoneCredentialsHook,
        AddMonitordKeystoneCredentialsHook,
        FixPuppetManifests,
        FixHostSystemRepoHook,
        SyncDnsHook,
        CopyOpenstackReleaseVersions,
        MoveKeysHook,
        RecreateNailgunInPriveleged,
        FixDhcrelayConf,
        FixDhcrelayMonitor,
        SetFixedVersionInSupervisor,
    ]

    def __init__(self, upgraders, config):
        #: Pre upgrade hook objects
        self.pre_upgrade_hooks = [hook_class(upgraders, config)
                                  for hook_class in self.hook_list]

    def run(self):
        """Run hooks if required
        """
        for hook in self.pre_upgrade_hooks:
            hook_name = hook.__class__.__name__

            if hook.is_required:
                logger.debug('Run pre upgarde hook %s', hook_name)
                hook.run()
            else:
                logger.debug('Skip pre upgrade hook %s', hook_name)
