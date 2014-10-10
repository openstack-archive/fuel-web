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

from nailgun.api.v1.handlers.base import content_json
from nailgun.api.v1.handlers.base import SingleHandler

from nailgun.api.v1.validators.master_node_settings \
    import MasterNodeSettingsValidator

from nailgun import objects
from nailgun import utils


class MasterNodeSettingsHandler(SingleHandler):

    single = objects.MasterNodeSettings

    validator = MasterNodeSettingsValidator

    @content_json
    def PATCH(self, obj_id):
        """Update settings for master node
        :http: * 200 (OK)
               * 400 (Invalid data)
               * 404 (Settings are not present in db)

        """
        data = self.checked_data(self.validator.validate_update)

        settings_instance = self.get_object_or_404(self.single, obj_id)

        settings_instance.settings = utils.dict_merge(
            settings_instance.settings, data["settings"]
        )

        return self.single.to_json(settings_instance)
