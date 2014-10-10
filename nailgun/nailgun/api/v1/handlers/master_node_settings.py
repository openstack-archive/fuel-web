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

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import content_json

from nailgun.api.v1.validators.master_node_settings \
    import MasterNodeSettingsValidator

from nailgun import objects
from nailgun import utils


class MasterNodeSettingsHandler(BaseHandler):

    single = objects.MasterNodeSettings

    validator = MasterNodeSettingsValidator

    def get_object_or_404(self, obj):
        """Get object instance

        Override parent class method in order to use obj.get_one method
        for retrieving instance

        Side effects:
        raise 404 http error if instance is not found in db

        Arguments:
        obj - nailgun object which method will be used

        return - instance in case of success
        """

        instance = obj.get_one()
        if not instance:
            raise self.http(404, u'{0} not found'.format(obj.__name__))

        return instance

    @content_json
    def GET(self):
        """Return json with master node settings
        :http: * 200 (OK)
               * 404 (Settings are not present in db)
        """
        settings_instance = self.get_object_or_404(self.single)

        return self.single.to_json(settings_instance)

    @content_json
    def PUT(self):
        """Set settings for master node
        :http: * 200 (OK)
               * 400 (Invalid data)
               * 404 (Settings are not present in db)
        """
        data = self.checked_data(self.validator.validate_update,
                                 json_schema=self.single.schema)

        settings_instance = self.get_object_or_404(self.single)

        self.single.update(settings_instance, data)

        return self.single.to_json(settings_instance)

    @content_json
    def PATCH(self):
        """Update settings for master node
        :http: * 200 (OK)
               * 400 (Invalid data)
               * 404 (Settings are not present in db)

        """
        data = self.checked_data(self.validator.validate_update,
                                 json_schema=self.single.schema)

        settings_instance = self.get_object_or_404(self.single)

        settings_instance.settings = utils.dict_merge(
            settings_instance.settings, data["settings"]
        )

        return self.single.to_json(settings_instance)
