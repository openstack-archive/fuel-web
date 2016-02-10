# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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


from nailgun.api.v1.handlers.base import CollectionHandler
from nailgun.api.v1.handlers.base import content
from nailgun.api.v1.handlers.base import SingleHandler
from nailgun.api.v1.validators.network import NetworkGroupValidator

from nailgun.errors import errors

from nailgun import objects


class NetworkGroupHandler(SingleHandler):
    """Network group handler"""

    validator = NetworkGroupValidator
    single = objects.NetworkGroup

    @content
    def PUT(self, obj_id):
        """:returns: JSONized NetworkGroup object.

        :http: * 200 (OK)
               * 400 (object cannot be updated)
               * 404 (object not found in db)
        """
        obj = self.get_object_or_404(self.single, obj_id)

        data = self.checked_data(
            self.validator.validate_update,
            instance=obj
        )
        try:
            self.single.update(obj, data)
        except errors.CannotUpdate as exc:
            raise self.http(400, exc.message)

        return self.single.to_json(obj)

    @content
    def DELETE(self, obj_id):
        """:returns: Empty string

        :http: * 204 (object successfully deleted)
               * 400 (object cannot be deleted)
               * 404 (object not found in db)
        """
        obj = self.get_object_or_404(
            self.single,
            obj_id
        )

        self.checked_data(
            self.validator.validate_delete,
            instance=obj
        )

        try:
            self.single.delete(obj)
        except errors.CannotDelete as exc:
            raise self.http(400, exc.message)

        raise self.http(204)


class NetworkGroupCollectionHandler(CollectionHandler):
    """Network group collection handler"""

    collection = objects.NetworkGroupCollection
    validator = NetworkGroupValidator
