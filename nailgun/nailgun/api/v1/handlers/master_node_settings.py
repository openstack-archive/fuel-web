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

from oslo_serialization import jsonutils

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

    def _handle_stats_opt_in(self, settings_data=None):
        """Starts task on stats user creation or removal

        :param settings_data: dict with master node settings.
        Current data from DB will be used if master_node_settings_data is None
        """
        must_send = self.single.must_send_stats(
            master_node_settings_data=settings_data)
        if must_send:
            logger.debug("Handling customer opt-in to sending statistics")
            manager = CreateStatsUserTaskManager()
        else:
            logger.debug("Handling customer opt-out to sending statistics")
            manager = RemoveStatsUserTaskManager()
        try:
            manager.execute()
        except Exception:
            logger.exception("Stats user operation failed")

    def _get_new_opt_in_status(self):
        """Extracts opt in status from request

        Returns None if no opt in status in the request

        :return: bool or None
        """
        data = self.checked_data(self.validator.validate_update)
        return data.get('settings', {}).get('statistics', {}).\
            get('send_anonymous_statistic', {}).get('value')

    def _perform_update(self, http_method):
        old_opt_in = self.single.must_send_stats()
        new_opt_in = self._get_new_opt_in_status()
        result = http_method()

        if new_opt_in is not None and old_opt_in != new_opt_in:
            self._handle_stats_opt_in(settings_data=jsonutils.loads(result))
        return result

    @content
    def PUT(self):
        return self._perform_update(
            super(MasterNodeSettingsHandler, self).PUT)

    @content
    def PATCH(self):
        return self._perform_update(
            super(MasterNodeSettingsHandler, self).PATCH)
