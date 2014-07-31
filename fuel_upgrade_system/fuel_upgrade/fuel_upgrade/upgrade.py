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

    :param upgraders: a list with upgrader classes to use; each upgrader
        must inherit the :class:`BaseUpgrader`
    :param no_rollback: call :meth:`BaseUpgrader.rollback` method
        in case of exception during execution
    """

    def __init__(self, upgraders, no_rollback=True):
        #: a list of upgraders to use
        self._upgraders = upgraders
        #: a list of used upgraders (needs by rollback feature)
        self._used_upgraders = []
        #: should we make rollback in case of error?
        self._rollback = not no_rollback

    def run(self):
        """Runs consequentially all registered upgraders.

        .. note:: in case of exception the `rollback` method will be called
        """
        logger.info('*** START UPGRADING')

        for upgrader in self._upgraders:

            try:
                logger.debug('%s: upgrading...', upgrader.__class__.__name__)
                self._used_upgraders.append(upgrader)
                upgrader.upgrade()
            except Exception as exc:
                logger.exception(
                    '%s: failed to upgrade: "%s"',
                    upgrader.__class__.__name__, exc)

                if self._rollback:
                    self.rollback()

                logger.error('*** UPGRADE FAILED')
                raise

        self._on_success()
        logger.info('*** UPGRADE DONE SUCCESSFULLY')

    def _on_success(self):
        """Run on_success method for engines,
        skip method call if there were some errors,
        because if upgrade succeed we shouldn't
        fail it.
        """
        for upgrader in self._upgraders:
            try:
                logger.debug(
                    '%s: run on_success method',
                    upgrader.__class__.__name__)
                upgrader.on_success()
            except Exception as exc:
                logger.exception(
                    '%s: skip the engine because failed to '
                    'execute on_success method: "%s"',
                    upgrader.__class__.__name__, exc)

    def rollback(self):
        logger.debug('Run rollback')

        while self._used_upgraders:
            upgrader = self._used_upgraders.pop()
            logger.debug('%s: rollbacking...', upgrader.__class__.__name__)
            upgrader.rollback()
