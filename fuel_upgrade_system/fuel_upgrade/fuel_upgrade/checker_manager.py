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

import six

from fuel_upgrade.engines.docker_engine import DockerInitializer
from fuel_upgrade.engines.docker_engine import DockerUpgrader
from fuel_upgrade.engines.host_system import HostSystemUpgrader
from fuel_upgrade.engines.openstack import OpenStackUpgrader

from fuel_upgrade.before_upgrade_checker import CheckFreeSpace
from fuel_upgrade.before_upgrade_checker import CheckNoRunningOstf
from fuel_upgrade.before_upgrade_checker import CheckNoRunningTasks
from fuel_upgrade.before_upgrade_checker import CheckRequiredVersion
from fuel_upgrade.before_upgrade_checker import CheckUpgradeVersions


logger = logging.getLogger(__name__)


class AttrDict(dict):
    """Dict as object where keys are object parameters
    """
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


class CheckerManager(object):
    """Checker manager

    :param list upgraders: list of :class:`BaseUpgrader` implementations
    :param config: :class:`Config` object
    """

    #: Mapping of checkers to upgrade engines
    CHECKERS_MAPPING = {
        DockerUpgrader: [
            CheckUpgradeVersions,
            CheckRequiredVersion,
            CheckFreeSpace,
            CheckNoRunningTasks,
            CheckNoRunningOstf],
        OpenStackUpgrader: [
            CheckFreeSpace,
            CheckNoRunningTasks],
        HostSystemUpgrader: [
            CheckFreeSpace],
        DockerInitializer: []}

    def __init__(self, upgraders, config):
        #: list of upgraders
        self.upgraders = upgraders
        required_free_spaces = [
            upgarde.required_free_space
            for upgarde in self.upgraders]

        #: context which checkers initialized with
        self.context = AttrDict(
            config=config,
            required_free_spaces=required_free_spaces)

    def check(self):
        """Runs checks
        """
        for checker in self._checkers():
            logger.debug('Start checker %s...', checker.__class__.__name__)
            checker.check()

    def _checkers(self):
        """Returns list initialized of checkers

        :returns: list of :class:`BaseBeforeUpgradeChecker` objects
        """
        checkers_classes = []
        for engine, checkers in six.iteritems(self.CHECKERS_MAPPING):
            if self._is_engine_enabled(engine):
                checkers_classes.extend(checkers)

        return [checker(self.context) for checker in set(checkers_classes)]

    def _is_engine_enabled(self, engine_class):
        """Checks if engine in the list

        :param list engines_list: list of engines
        :param engine_class: engine class

        :returns: True if engine in the list
                  False if engine not in the list
        """
        engines = filter(
            lambda engine: isinstance(engine, engine_class),
            self.upgraders)
        if engines:
            return True

        return False
