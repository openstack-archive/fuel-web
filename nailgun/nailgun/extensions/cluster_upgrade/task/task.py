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

from nailgun.db import db
from nailgun.logger import logger
from nailgun.orchestrator import deployment_graph
from nailgun.orchestrator import deployment_serializers
from nailgun.task import task as nailgun_task


class UpgradeTask(object):

    @classmethod
    def message(cls, task, nodes):
        logger.debug("%s.message(task=%s)", cls.__class__.__name__, task.uuid)

        for n in nodes:
            if n.pending_roles:
                n.roles += n.pending_roles
                n.pending_roles = []
            n.status = 'provisioned'
            n.progress = 0

        orchestrator_graph = deployment_graph.AstuteGraph(task.cluster)

        serialized_cluster = deployment_serializers.serialize(
            orchestrator_graph, task.cluster, nodes)

        # After serialization set pending_addition to False
        for node in nodes:
            node.pending_addition = False

        rpc_message = nailgun_task.make_astute_message(
            task,
            'deploy',
            'deploy_resp',
            {
                'deployment_info': serialized_cluster
            }
        )
        db().flush()
        return rpc_message
