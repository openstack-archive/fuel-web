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
from nailgun.api.v1.handlers.base import SingleHandler

from nailgun.api.v1.validators.master_node_settings \
    import MasterNodeSettingsValidator

from nailgun.errors import errors

from nailgun import objects
from nailgun import utils


class MasterNodeSettingsHandler(SingleHandler):

    single = objects.MasterNodeSettings

    validator = MasterNodeSettingsValidator

    def get_one_or_404(self):
        try:
            instance = self.single.get_one(fail_if_not_found=True)
        except errors.ObjectNotFound:
            raise self.http(404, "Settings are not found in db")

        return instance

    @content
    def GET(self):
        """Get master node settings
        :http: * 200 (OK)
               * 404 (Settings are not found in db)
        """
        instance = self.get_one_or_404()

        return self.single.to_json(instance)

    @content
    def PUT(self):
        """Change settings for master node
        :http: * 200 (OK)
               * 400 (Invalid data)
               * 404 (Settings are not present in db)
        """
        data = self.checked_data(self.validator.validate_update)

        instance = self.get_one_or_404()

        self.single.update(instance, data)

        return self.single.to_json(instance)

    @content
    def PATCH(self):
        """Update settings for master node
        :http: * 200 (OK)
               * 400 (Invalid data)
               * 404 (Settings are not present in db)

        """
        data = self.checked_data(self.validator.validate_update)

        instance = self.get_one_or_404()

        instance.settings = utils.dict_merge(
            instance.settings, data["settings"]
        )

        return self.single.to_json(instance)
