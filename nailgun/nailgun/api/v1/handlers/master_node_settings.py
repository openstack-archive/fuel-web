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

from nailgun.api.v1.handlers.base import content
from nailgun.api.v1.handlers.base import DBSingletonHandler
from nailgun.api.v1.validators.master_node_settings \
    import MasterNodeSettingsValidator
from nailgun.logger import logger
from nailgun import objects
from nailgun.task.manager import CreateStatsUserTaskManager
from nailgun.task.manager import RemoveStatsUserTaskManager


class MasterNodeSettingsHandler(DBSingletonHandler):

    single = objects.MasterNodeSettings

    validator = MasterNodeSettingsValidator

    not_found_error = "Settings are not found in DB"

    def _handle_stats_opt_in(self):
        if self.single.must_send_stats():
            logger.debug("Handling customer opt-in to sending statistics")
            try:
                manager = CreateStatsUserTaskManager()
                manager.execute()
            except Exception:
                logger.exception("Creating stats user failed")
        else:
            logger.debug("Handling customer opt-out to sending statistics")
            try:
                manager = RemoveStatsUserTaskManager()
                manager.execute()
            except Exception:
                logger.exception("Removing stats user failed")

    @content
    def PUT(self):
        result = super(MasterNodeSettingsHandler, self).PUT()
        self._handle_stats_opt_in()
        return result

    @content
    def PATCH(self):
        result = super(MasterNodeSettingsHandler, self).PATCH()
        self._handle_stats_opt_in()
        return result
