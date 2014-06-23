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

from fuel_upgrade.actions import ActionManager
from fuel_upgrade.engines.base import UpgradeEngine
from fuel_upgrade.utils import get_required_size_for_actions


logger = logging.getLogger(__name__)


class BootstrapUpgrader(UpgradeEngine):
    """Bootstrap Upgrader.
    """

    def __init__(self, *args, **kwargs):
        super(BootstrapUpgrader, self).__init__(*args, **kwargs)

        #: an action manager instance
        self._action_manager = ActionManager(self.config.bootstrap['actions'])

    def upgrade(self):
        logger.info('bootstrap upgrader: starting...')

        self._action_manager.do()

        logger.info('bootstrap upgrader: done')

    def rollback(self):
        logger.info('bootstrap upgrader: rollbacking...')

        self._action_manager.undo()

        logger.info('bootstrap upgrader: rollbacked')

    @property
    def required_free_space(self):
        return get_required_size_for_actions(
            self.config.bootstrap['actions'], self.config.update_path
        )
