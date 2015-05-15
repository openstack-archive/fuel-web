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

import glob
import logging

import six

from fuel_upgrade import utils
from fuel_upgrade.version_file import VersionFile

from fuel_upgrade.engines.host_system import HostSystemUpgrader


logger = logging.getLogger(__name__)


class UpgradeManager(object):
    """Upgrade manager is used to orchestrate upgrading process.

    :param upgraders: a list with upgrader classes to use; each upgrader
        must inherit the :class:`BaseUpgrader`
    :param no_rollback: call :meth:`BaseUpgrader.rollback` method
        in case of exception during execution
    """

    def __init__(self, upgraders, config, no_rollback=True):
        #: an object with configuration context
        self._config = config
        #: a list of upgraders to use
        self._upgraders = upgraders
        #: a list of used upgraders (needs by rollback feature)
        self._used_upgraders = []
        #: should we make rollback in case of error?
        self._rollback = not no_rollback
        #: version.yaml manager
        self._version_file = VersionFile(self._config)
        self._version_file.save_current()

    def run(self):
        """Runs consequentially all registered upgraders.

        .. note:: in case of exception the `rollback` method will be called
        """
        logger.info('*** START UPGRADING')

        self._version_file.switch_to_new()

        for upgrader in self._upgraders:
            logger.debug('%s: backuping...', upgrader.__class__.__name__)

            try:
                upgrader.backup()
            except Exception as exc:
                logger.exception(
                    '%s: failed to backup: "%s"',
                    upgrader.__class__.__name__, exc)

                logger.error('*** UPGRADE FAILED')
                raise

        for upgrader in self._upgraders:
            logger.debug('%s: upgrading...', upgrader.__class__.__name__)
            self._used_upgraders.append(upgrader)

            try:
                upgrader.upgrade()
            except Exception as exc:
                logger.exception(
                    '%s: failed to upgrade: "%s"',
                    upgrader.__class__.__name__, exc)

                if self._rollback:
                    self.rollback()

                logger.error('*** UPGRADE FAILED')
                raise

        try:
            self._on_success()
        except Exception as exc:
            logger.exception(
                'Could not complete on_success actions due to %s',
                six.text_type(exc))

        logger.info('*** UPGRADE DONE SUCCESSFULLY')

    def _on_success(self):
        """Do some useful job if upgrade was done successfully.
        """
        # Remove saved version files for all upgrades
        #
        # NOTE(eli): It solves several problems:
        #
        # 1. user runs upgrade 5.0 -> 5.1 which fails
        # upgrade system saves version which we upgrade
        # from in file working_dir/5.1/version.yaml.
        # Then user runs upgrade 5.0 -> 5.0.1 which
        # successfully upgraded. Then user runs again
        # upgrade 5.0.1 -> 5.1, but there is saved file
        # working_dir/5.1/version.yaml which contains
        # 5.0 version, and upgrade system thinks that
        # it's upgrading from 5.0 version, as result
        # it tries to make database dump from wrong
        # version of container.
        #
        # 2. without this hack user can run upgrade
        # second time and loose his data, this hack
        # prevents this case because before upgrade
        # checker will use current version instead
        # of saved version to determine version which
        # we run upgrade from.
        for version_file in glob.glob(self._config.version_files_mask):
            utils.remove(version_file)

    def rollback(self):
        logger.debug('Run rollback')

        # because of issue #1452378 [1], we have to perform HostSystem's
        # rollback before others. so, move it to the end of list.
        #
        # [1]: https://bugs.launchpad.net/fuel/+bug/1452378
        hostsystem = next((
            upgrader for upgrader in self._used_upgraders
            if isinstance(upgrader, HostSystemUpgrader)),
            None)
        if hostsystem is not None:
            self._used_upgraders.remove(hostsystem)
            self._used_upgraders.append(hostsystem)

        # do rollback in reverse order for all the upgraders
        while self._used_upgraders:
            upgrader = self._used_upgraders.pop()
            logger.debug('%s: rollbacking...', upgrader.__class__.__name__)
            upgrader.rollback()

        self._version_file.switch_to_previous()
