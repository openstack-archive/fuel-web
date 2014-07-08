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

from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase


class PreUpgradeHookManager(object):
    """
    """

    def __init__(self, upgraders, config):
        pre_upgrade_hooks_cls = PreUpgradeHookBase.__subclasses__()

        #: Pre upgrade hook objects
        self.pre_upgrade_hooks = [hook_class(upgraders, config)
                                  for hook_class in pre_upgrade_hooks_cls]

    def run(self):
        for hook in self.pre_upgrade_hooks:
            if hook.is_enabled_for_engines and hook.is_required:
                hook.run()
