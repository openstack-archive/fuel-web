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

from fuel_upgrade import errors
from fuel_upgrade import utils


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

    def __init__(self, source_path, config, upgraders, no_rollback=True,
                 no_check=False):
        self._source_path = source_path
        self._upgraders = [
            upgrader(source_path, config) for upgrader in upgraders
        ]
        self._rollback = not no_rollback
        self._check = not no_check
        self.config = config

    def run(self):
        """Runs consequentially all registered upgraders.

        .. note:: in case of exception the `rollback` method will be called
        """
        self.before_upgrade()

        for upgrader in self._upgraders:

            try:
                logger.debug(
                    '%s: upgrading...', upgrader.__class__.__name__)
                upgrader.upgrade()
                self.after_upgrade_checks()
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
        if self._check:
            self.check_upgrade_opportunity()

    def after_upgrade_checks(self):
        logger.debug('Run after upgrade actions')
        self.check_health()

    def make_backup(self):
        for upgrader in self._upgraders:
            logger.debug('%s: backuping data...', upgrader.name)
            upgrader.backup()

    def check_upgrade_opportunity(self):
        """Sends request to nailgun
        to make sure that there are no
        running tasks

        TODO(eli): move this logic to separate
        class
        """
        logger.info('Check upgrade opportunity')
        nailgun = self.config.endpoints['nailgun']
        tasks_url = 'http://{0}:{1}/api/v1/tasks'.format(
            nailgun['host'], nailgun['port'])

        tasks = utils.get_request(tasks_url)

        running_tasks = filter(
            lambda t: t['status'] == 'running', tasks)

        if running_tasks:
            tasks_msg = ['id={0} cluster={1} name={2}'.format(
                t.get('id'),
                t.get('cluster'),
                t.get('name')) for t in running_tasks]

            error_msg = 'Cannot run upgrade, tasks are running: {0}'.format(
                ' '.join(tasks_msg))

            raise errors.CannotRunUpgrade(error_msg)

    def check_health(self):
        # TODO(eli): implementation is required
        logger.debug('Check that upgrade passed correctly')

    def rollback(self):
        logger.debug('Run rollback')

        for upgrader in reversed(self._upgraders):
            upgrader.rollback()
