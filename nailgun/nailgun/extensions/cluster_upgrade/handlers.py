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

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.decorators import handle_errors
from nailgun.api.v1.handlers.decorators import to_json
from nailgun.api.v1.handlers.decorators import validate
from nailgun import objects
from nailgun.task import manager

from . import upgrade
from . import validators
from .objects import adapters


class ClusterUpgradeCloneHandler(BaseHandler):
    single = objects.Cluster
    validator = validators.ClusterUpgradeValidator

    @handle_errors
    @validate
    @to_json
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
        return new_cluster.to_dict()


class NodeReassignHandler(BaseHandler):
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

    @handle_errors
    @validate
    @to_json
    def POST(self, cluster_id):
        """Reassign node to the given cluster.

        The given node will be assigned from the current cluster to the
        given cluster, by default it involves the reprovisioning of this
        node. If the 'reprovision' flag is set to False, then the node
        will be just reassigned. If the 'roles' list is specified, then
        the given roles will be used as 'pending_roles' in case of
        the reprovisioning or otherwise as 'roles'.

        :param cluster_id: ID of the cluster node should be assigned to.
        :returns: None
        :http: * 202 (OK)
               * 400 (Incorrect node state, problem with task execution,
                      conflicting or incorrect roles)
               * 404 (Cluster or node not found)
        """
        cluster = adapters.NailgunClusterAdapter(
            self.get_object_or_404(self.single, cluster_id))

        data = self.checked_data(cluster=cluster)
        node = adapters.NailgunNodeAdapter(
            self.get_object_or_404(objects.Node, data['node_id']))
        reprovision = data.get('reprovision', True)
        given_roles = data.get('roles', [])

        roles, pending_roles = upgrade.UpgradeHelper.get_node_roles(
            reprovision, node.roles, given_roles)
        upgrade.UpgradeHelper.assign_node_to_cluster(
            node, cluster, roles, pending_roles)

        if reprovision:
            self.handle_task(cluster_id, [node.node])


class CopyVIPsHandler(BaseHandler):
    single = objects.Cluster
    validator = validators.CopyVIPsValidator

    @handle_errors
    @validate
    @to_json
    def POST(self, cluster_id):
        """Copy VIPs from original cluster to new one

        Original cluster object is obtained from existing relation between
        clusters that is created on cluster clone operation

        :param cluster_id: id of cluster that VIPs must be copied to

        :http: * 200 (OK)
               * 400 (validation failed)
               * 404 (seed cluster is not found)
        """
        from .objects import relations

        cluster = self.get_object_or_404(self.single, cluster_id)
        relation = relations.UpgradeRelationObject.get_cluster_relation(
            cluster.id)

        self.checked_data(cluster=cluster, relation=relation)

        # get original cluster object and create adapter with it
        orig_cluster_adapter = \
            adapters.NailgunClusterAdapter(
                adapters.NailgunClusterAdapter.get_by_uid(
                    relation.orig_cluster_id)
            )

        seed_cluster_adapter = adapters.NailgunClusterAdapter(cluster)

        upgrade.UpgradeHelper.copy_vips(orig_cluster_adapter,
                                        seed_cluster_adapter)
