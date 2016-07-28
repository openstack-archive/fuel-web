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

import traceback

import six
import web

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import SingleHandler
from nailgun.api.v1.handlers.decorators import handle_errors
from nailgun.api.v1.handlers.decorators import serialize
from nailgun.api.v1.handlers.decorators import validate
from nailgun.api.v1.validators.openstack_config import OpenstackConfigValidator
from nailgun import errors
from nailgun.logger import logger
from nailgun import objects
from nailgun.task.manager import OpenstackConfigTaskManager


class OpenstackConfigCollectionHandler(BaseHandler):

    validator = OpenstackConfigValidator

    @handle_errors
    @validate
    @serialize
    def GET(self):
        """Returns list of filtered config objects.

        :http: * 200 (OK)
               * 400 (Invalid query specified)
        :return: List of config objects in JSON format.
        """
        data = self.checked_data(
            self.validator.validate_query, data=web.input())
        return objects.OpenstackConfigCollection.to_list(
            objects.OpenstackConfigCollection.filter_by(None, **data))

    @handle_errors
    @validate
    def POST(self):
        """Creates new config object.

        If config object with specified parameters exists, it is replaced
        with a new config object. Previous object is marked as inactive.
        It can be retrieved to track the history of configuration changes.

        :http: * 201 (Object successfully created)
               * 400 (Invalid query specified)
               * 404 (Object dependencies not found)
        :reutrn: New config object in JSON format.
        """
        data = self.checked_data()
        configs = objects.OpenstackConfigCollection.create(data)
        raise self.http(
            201, objects.OpenstackConfigCollection.to_json(configs))


class OpenstackConfigHandler(SingleHandler):

    single = objects.OpenstackConfig
    validator = OpenstackConfigValidator

    @handle_errors
    @validate
    def PUT(self, obj_id):
        """Update an existing configuration is not allowed

        :http: * 405 (Method not allowed)
        """
        raise self.http(405)

    @handle_errors
    @validate
    def DELETE(self, obj_id):
        """:returns: Empty string

        :http: * 204 (object successfully deleted)
               * 400 (object is already deleted)
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
            self.single.disable(obj)
        except errors.CannotUpdate as exc:
            raise self.http(400, exc.message)

        raise self.http(204)


class OpenstackConfigExecuteHandler(BaseHandler):

    validator = OpenstackConfigValidator
    task_manager = OpenstackConfigTaskManager

    @handle_errors
    @validate
    def PUT(self):
        """Executes update tasks for specified resources.

        :http: * 200 (OK)
               * 202 (Accepted)
               * 400 (Invalid data)
               * 404 (Object dependencies not found)
        """
        graph_type = web.input(graph_type=None).graph_type or None
        filters = self.checked_data(self.validator.validate_execute)

        cluster = self.get_object_or_404(
            objects.Cluster, filters['cluster_id'])

        # Execute upload task for nodes
        task_manager = self.task_manager(cluster_id=cluster.id)
        try:
            task = task_manager.execute(filters, graph_type=graph_type)
        except Exception as exc:
            logger.warn(
                u'Cannot execute %s task nodes: %s',
                self.task_manager.__name__, traceback.format_exc())
            raise self.http(400, six.text_type(exc))

        self.raise_task(task)
