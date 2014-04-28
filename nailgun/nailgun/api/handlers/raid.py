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

"""
Handlers dealing with RAIDs
"""
import traceback

from nailgun.raid.manager import RaidManager

from nailgun.api.handlers.base import BaseHandler
from nailgun.api.handlers.base import content_json

from nailgun.db import db
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import NodeRaidConfiguration
from nailgun.db.sqlalchemy.models import Task as TaskModel

from nailgun.logger import logger
from nailgun.objects import Task
from nailgun.task.manager import ApplyNodeRAIDConfigurationTaskManager
from nailgun.task.task import ApplyNodeRAIDConfigurationTask


class NodeRaidHandler(BaseHandler):
    """Node RAID configuration handler
    """
    model = NodeRaidConfiguration

    @content_json
    def GET(self, node_id):
        """:returns: Current node's RAID configuration.
        :http: * 200 (OK)
               * 404 (node or its raid config not found in db)
        """
        node = self.get_object_or_404(Node, node_id)
        if not node.raids:
            raise self.http(404)

        return node.raids.config

    @content_json
    def PUT(self, node_id):
        """Update node RAID configuration.
        :http: * 200 (OK)
               * 404 (node not found in db)
        """
        node = self.get_object_or_404(Node, node_id)
        data = self.checked_data()

        db().query(NodeRaidConfiguration).filter_by(node_id=node_id).update(
            {'config': data})
        db().flush()
        db().refresh(node)

        return node.raids.config


class NodeDefaultsRaidHandler(BaseHandler):
    """Node default RAID handler
    """

    @content_json
    def GET(self, node_id):
        """:returns: JSONized RAID configuration.
        """
        node = self.get_object_or_404(Node, node_id)
        default_raid_conf = self.get_default(node)
        return default_raid_conf

    def get_default(self, node):
        return RaidManager.get_default_raid_configuration(node)


class NodeRaidApplyHandler(BaseHandler):
    """Node RAID configration applying handler
    """

    @content_json
    def GET(self, node_id):
        """:returns: Current node's RAID configration in a way
        that it will be sent to Astute
        """
        node = self.get_object_or_404(Node, node_id)
        task = TaskModel(uuid="dryrun")

        return ApplyNodeRAIDConfigurationTask.message(task, node)

    @content_json
    def PUT(self, node_id):
        """Trigger applying of the node's RAID configuration.
        :returns: JSONized Task object.
        :http: * 202 (accepted)
               * 400 (applying task failed)
               * 404 (node not found in db)
        """
        node = self.get_object_or_404(Node, node_id)
        task_manager = ApplyNodeRAIDConfigurationTaskManager()
        try:
            task = task_manager.execute(node)
        except Exception as exc:
            logger.warn(u'Cannot execute {0} task nodes: {1}'.format(
                task_manager.__class__.__name__, traceback.format_exc()))
            raise self.http(400, message=str(exc))

        raise self.http(202, Task.to_json(task))
