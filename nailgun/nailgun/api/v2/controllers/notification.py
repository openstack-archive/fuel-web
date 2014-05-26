# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

"""
Handlers dealing with notifications
"""
import pecan

from nailgun.api.v2.controllers.base import BaseController

from nailgun import objects

from nailgun.api.v1.validators.notification import NotificationValidator
from nailgun.db import db


class NotificationController(BaseController):

    single = objects.Notification
    collection = objects.NotificationCollection
    validator = NotificationValidator

    @pecan.expose(template='json:', content_type='application/json')
    def put_all(self):
        """:returns: Collection of JSONized Notification objects.
        :http: * 200 (OK)
               * 400 (invalid data specified for collection update)
        """
        request = pecan.request
        data = self.validator.validate_collection_update(
            request.body
        )

        notifications_updated = []
        for nd in data:
            notif = self.collection.single.get_by_uid(nd["id"])
            notif.update(nd)
            notifications_updated.append(notif)
            db().add(notif)
        return self.collection.to_json(notifications_updated)
