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

logger = logging.getLogger(__name__)


class UpgradeManager(object):
    """Upgrade manager is used to orchestrate upgrading process.

    :param source_path: a path to folder with upgrade files
    :param upgraders: a list with upgrader classes to use; each upgrader
        must inherit the :class:`BaseUpgrader`
    :param no_rollback: call :meth:`BaseUpgrader.rollback` method
        in case of exception during execution
    :param no_check: do not make opportunity check before upgrades
    """

    def __init__(self, upgraders, checkers, no_rollback=True):
        self._upgraders = upgraders
        self._checkers = checkers
        self._rollback = not no_rollback

    def run(self):
        """Runs consequentially all registered upgraders.

        .. note:: in case of exception the `rollback` method will be called
        """
        self.before_upgrade()

        for upgrader in self._upgraders:

            try:
                logger.debug(
                    '%s: upgrading...', upgrader.__class__.__name__)
                upgrader.before_upgrade_actions()
                upgrader.upgrade()
                upgrader.post_upgrade_actions()

            except Exception as exc:
                logger.exception(
                    '%s: failed to upgrade: "%s"',
                    upgrader.__class__.__name__, exc)

                if self._rollback:
                    logger.debug(
                        '%s: rollbacking...', upgrader.__class__.__name__)
                    self.rollback()

                raise

    def before_upgrade(self):
        logger.debug('Run before upgrade actions')
        if self._checkers:
            for checker in self._checkers:
                checker.check()

    def rollback(self):
        logger.debug('Run rollback')

        for upgrader in reversed(self._upgraders):
            upgrader.rollback()
