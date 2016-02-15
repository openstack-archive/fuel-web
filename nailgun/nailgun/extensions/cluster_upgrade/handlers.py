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

import six

from nailgun.api.v1.handlers import base
from nailgun import objects
from nailgun.task import manager

from . import upgrade
from . import validators
from .objects import adapters


class ClusterUpgradeCloneHandler(base.BaseHandler):
    single = objects.Cluster
    validator = validators.ClusterUpgradeValidator

    @base.content
    def POST(self, cluster_id):
        """Initialize the upgrade of the cluster.

        Creates a new cluster with specified name and release_id. The
        new cluster is created with parameters that are copied from the
        cluster with the given cluster_id. The values of the generated
        and editable attributes are just copied from one to the other.

        :param cluster_id: ID of the cluster from which parameters would
                           be copied
        :returns: JSON representation of the created cluster
        :http: * 200 (OK)
               * 400 (upgrade parameters are invalid)
               * 404 (node or release not found in db)
        """
        orig_cluster = adapters.NailgunClusterAdapter(
            self.get_object_or_404(self.single, cluster_id))
        request_data = self.checked_data(cluster=orig_cluster)
        new_cluster = upgrade.UpgradeHelper.clone_cluster(orig_cluster,
                                                          request_data)
        return new_cluster.to_json()


class NodeReassignHandler(base.BaseHandler):
    single = objects.Cluster
    validator = validators.NodeReassignValidator
    task_manager = manager.ProvisioningTaskManager

    def handle_task(self, cluster_id, nodes):
        try:
            task_manager = self.task_manager(cluster_id=cluster_id)
            task = task_manager.execute(nodes)
        except Exception as exc:
            raise self.http(400, msg=six.text_type(exc))

        self.raise_task(task)

    @base.content
    def POST(self, cluster_id):
        """Reassign node to the given cluster.

        The given node will be assigned from the current cluster to the
        given cluster, by default it includes re-provisioning and redeployment
        of this node. If the 'reprovision' flag is set to False, then the node
        will be just reassigned include an ability to change roles of the node
        during this procedure by setting the 'roles' flag.

        :param cluster_id: ID of the cluster which node should be
                           assigned to.
        :returns: None
        :http: * 202 (OK)
               * 400 (Incorrect node state or problem with task execution)
               * 404 (Cluster or node not found)
        """
        cluster = adapters.NailgunClusterAdapter(
            self.get_object_or_404(self.single, cluster_id))

        data = self.checked_data(cluster=cluster)
        reprovision = data['reprovision']
        node = adapters.NailgunNodeAdapter(
            self.get_object_or_404(objects.Node, data['node_id']))

        if reprovision:
            roles, pending_roles = [], node.roles
        else:
            roles, pending_roles = data['roles'], []

        upgrade.UpgradeHelper.assign_node_to_cluster(
            node, cluster, roles, pending_roles)

        if reprovision:
            self.handle_task(cluster_id, [node.node])
