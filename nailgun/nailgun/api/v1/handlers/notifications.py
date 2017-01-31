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
import web

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import CollectionHandler
from nailgun.api.v1.handlers.base import handle_errors
from nailgun.api.v1.handlers.base import serialize
from nailgun.api.v1.handlers.base import SingleHandler
from nailgun.api.v1.handlers.base import validate
from nailgun.api.v1.validators.notification import NotificationValidator
from nailgun import objects


class NotificationHandler(SingleHandler):
    """Notification single handler"""

    single = objects.Notification
    validator = NotificationValidator


class NotificationCollectionHandler(CollectionHandler):

    collection = objects.NotificationCollection
    validator = NotificationValidator

    @handle_errors
    @validate
    @serialize
    def PUT(self):
        """:returns: Collection of JSONized Notification objects.

        :http: * 200 (OK)
               * 400 (invalid data specified for collection update)
        """
        data = self.validator.validate_collection_update(web.data())

        notifications_updated = []
        for nd in data:
            notif = self.collection.single.get_by_uid(nd["id"])
            self.collection.single.update(notif, nd)
            notifications_updated.append(notif)
        return self.collection.to_list(notifications_updated)


class NotificationCollectionStatsHandler(CollectionHandler):

    collection = objects.NotificationCollection
    validator = NotificationValidator

    @handle_errors
    @validate
    @serialize
    def GET(self):
        """Calculates notifications statuses

        Counts all presented notifications in the DB and returns dict
        with structure {'total': count, 'unread': count, ...}

        :returns: dict with notifications statuses count

        :http: * 200 (OK)
        """
        return self.collection.single.get_statuses_with_count()

    @handle_errors
    @validate
    def POST(self):
        """Update notification statuses is not allowed

        :http: * 405 (Method not allowed)
        """
        raise self.http(405)


class NotificationStatusHandler(BaseHandler):

    validator = NotificationValidator

    @handle_errors
    @validate
    @serialize
    def PUT(self):
        """Updates status of all notifications

        :http: * 200 (OK)
               * 400 (Invalid data)
        """
        web_data = web.data()
        data = self.validator.validate_change_status(web_data)
        status = data['status']
        objects.NotificationCollection.update_statuses(status)
