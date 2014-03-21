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
import traceback

from os import path

from fuel_upgrade.utils import exec_cmd

logger = logging.getLogger(__name__)


class PuppetUpgrader(object):
    """Puppet implementation of upgrader

    TODO (eli): exact commands and unit
    tests will be added later
    """
    puppet_modules_dir = 'puppet_modules'

    def __init__(self, update_path):
        puppet_modules_path = path.join(update_path, self.puppet_modules_dir)
        self.puppet_cmd = 'puppet apply --debug --modulepath={0} -e '.format(
            puppet_modules_path)

    def upgrade(self):
        exec_cmd(self.puppet_cmd + '"include upgrade"')

    def rollback(self):
        exec_cmd(self.puppet_cmd + '"include rollback"')

    def backup(self):
        exec_cmd(self.puppet_cmd + '"include backup"')


class Upgrade(object):
    """Upgrade logic
    """

    def __init__(self,
                 update_path,
                 working_dir,
                 upgrade_engine,
                 disable_rollback=False):

        logger.debug(
            'Create Upgrade object with update path "{0}", '
            'working directory "{1}", '
            'upgrade engine "{2}", '
            'disable rollback is "{3}"'.format(
                update_path, working_dir,
                upgrade_engine.__class__.__name__,
                disable_rollback))

        self.update_path = update_path
        self.working_dir = working_dir
        self.upgrade_engine = upgrade_engine
        self.disable_rollback = disable_rollback

    def run(self):
        self.before_upgrade()

        try:
            self.upgrade()
            self.after_upgrade()
        except Exception as exc:
            logger.error('Upgrade failed: {0}'.format(exc))
            logger.error(traceback.format_exc())
            if not self.disable_rollback:
                self.rollback()

    def before_upgrade(self):
        logger.debug('Run before upgrade actions')
        self.check_upgrade_opportunity()
        self.shutdown_services()
        self.make_backup()

    def upgrade(self):
        logger.debug('Run upgrade')
        self.upgrade_engine.upgrade()

    def after_upgrade(self):
        logger.debug('Run after upgrade actions')
        self.run_services()
        self.check_health()

    def make_backup(self):
        logger.debug('Make backup')
        self.upgrade_engine.backup()

    def check_upgrade_opportunity(self):
        """Sends request to nailgun
        to make sure that there are no
        running tasks
        """
        logger.debug('Check upgrade opportunity')

    def run_services(self):
        logger.debug('Run services')

    def shutdown_services(self):
        logger.debug('Shutdown services')

    def check_health(self):
        logger.debug('Check that upgrade passed correctly')

    def rollback(self):
        logger.debug('Run rollback')
        self.upgrade_engine.rollback()
