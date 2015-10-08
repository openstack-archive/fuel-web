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

import abc
import copy
import six

from fuel_upgrade.config import read_yaml_config
from fuel_upgrade import utils


@six.add_metaclass(abc.ABCMeta)
class PreUpgradeHookBase(object):
    """Abstract class for pre upgrade hooks

    :param list upgraders: list of :class:`BaseUpgrader` implementations
    :param config: :class:`Config` object
    """

    def __init__(self, upgraders, config):
        #: config for upgrade
        self.config = config
        #: list of upgrade engines
        self.upgraders = upgraders

    @abc.abstractmethod
    def check_if_required(self):
        """Return True if check is required and False if is not required"""

    @abc.abstractmethod
    def run(self):
        """Run pre upgrade hook"""

    @abc.abstractproperty
    def enable_for_engines(self):
        """Return list of upgrade engines which the hook is required for"""

    @property
    def is_required(self):
        """Checks if it's required to run the hook

        :returns: True if required, False if is not required
        """
        return self.is_enabled_for_engines and self.check_if_required()

    @property
    def is_enabled_for_engines(self):
        """Checks if engine in the list

        :returns: True if engine in the list
                  False if engine not in the list
        """
        for engine in self.enable_for_engines:
            for upgrade in self.upgraders:
                if isinstance(upgrade, engine):
                    return True

        return False

    def update_astute_config(self, defaults=None, overwrites=None):
        """Update astute config and backup old one

        Read astute.yaml config file, update it with new config,
        copy old file to backup location and save new astute.yaml.
        """
        # NOTE(ikalnitsky): we need to re-read astute.yaml in order protect
        # us from loosing some useful injection of another hook
        astute_config = copy.deepcopy(defaults or {})
        astute_config = utils.dict_merge(
            astute_config,
            read_yaml_config(self.config.current_fuel_astute_path))
        astute_config = utils.dict_merge(
            astute_config,
            overwrites or {})

        # NOTE(eli): Just save file for backup in case
        # if user wants to restore it manually
        utils.copy_file(
            self.config.current_fuel_astute_path,
            '{0}_{1}'.format(self.config.current_fuel_astute_path,
                             self.config.from_version),
            overwrite=False)

        utils.save_as_yaml(self.config.current_fuel_astute_path, astute_config)
