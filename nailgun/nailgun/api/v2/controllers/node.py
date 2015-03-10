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
Controllers dealing with nodes
"""

from datetime import datetime

import pecan

from nailgun.api.v2.controllers.base import BaseController

from nailgun.api.v2.controllers.disks import NodeDisksController
from nailgun.api.v2.controllers.disks import NodeVolumesInformationController

from nailgun.api.v1.validators.network import NetAssignmentValidator
from nailgun.api.v1.validators.node import NodeValidator

from nailgun import consts
from nailgun import objects

from nailgun.objects.serializers.node import NodeInterfacesSerializer

from nailgun.db import db
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import NodeNICInterface
from nailgun.task.manager import NodeDeletionTaskManager

from nailgun.logger import logger
from nailgun import notifier


class NodeAgentController(BaseController):

    collection = objects.NodeCollection
    validator = NodeValidator

    @pecan.expose(template='json:', content_type='application/json')
    def put(self):
        """:returns: node id.
        :http: * 200 (node are successfully updated)
               * 304 (node data not changed since last request)
               * 400 (invalid nodes data specified)
               * 404 (node not found)
        """
        request = pecan.request
        nd = self.checked_data(
            self.validator.validate_collection_update,
            data=u'[{0}]'.format(request.body))[0]

        node = self.collection.single.get_by_meta(nd)

        if not node:
            raise self.http(404, "Can't find node: {0}".format(nd))

        node.timestamp = datetime.now()
        if not node.online:
            node.online = True
            msg = u"Node '{0}' is back online".format(node.human_readable_name)
            logger.info(msg)
            notifier.notify("discover", msg, node_id=node.id)
        db().flush()

        if 'agent_checksum' in nd and (
            node.agent_checksum == nd['agent_checksum']
        ):
            return {'id': node.id, 'cached': True}

        self.collection.single.update_by_agent(node, nd)
        return {"id": node.id}


class NodeNICsDefaultController(BaseController):
    """Node default network interfaces handler
    """

    @pecan.expose(template='json:', content_type='application/json')
    def get_one(self, node_id):
        """:returns: Collection of default JSONized interfaces for node.
        :http: * 200 (OK)
               * 404 (node not found in db)
        """
        node = self.get_object_or_404(objects.Node, node_id)
        return self.get_default(node)

    def get_default(self, node):
        if node.cluster:
            return objects.Node.get_network_manager(
                node
            ).get_default_networks_assignment(node)


class NodeCollectionNICsDefaultController(NodeNICsDefaultController):
    """Node collection default network interfaces handler
    """

    validator = NetAssignmentValidator

    @pecan.expose(template='json:', content_type='application/json')
    def get_all(self):
        """May receive cluster_id parameter to filter list
        of nodes

        :returns: Collection of JSONized Nodes interfaces.
        :http: * 200 (OK)
               * 404 (node not found in db)
        """
        cluster_id = pecan.request.GET.get('cluster_id')

        if cluster_id:
            nodes = \
                objects.NodeCollection.filter_by(None, cluster_id=cluster_id)
        else:
            nodes = objects.NodeCollection.all()

        return filter(lambda x: x is not None, map(self.get_default, nodes))


class NodeNICsController(BaseController):
    """Node network interfaces handler
    """

    # TODO(pkaminski): all NICs urls have to be unified
    collection_default_assignment = NodeCollectionNICsDefaultController()
    default_assignment = NodeNICsDefaultController()

    model = NodeNICInterface
    validator = NetAssignmentValidator
    serializer = NodeInterfacesSerializer

    @pecan.expose(template='json:', content_type='application/json')
    def get_one(self, node_id):
        """:returns: Collection of JSONized Node interfaces.
        :http: * 200 (OK)
               * 404 (node not found in db)
        """
        node = self.get_object_or_404(objects.Node, node_id)
        return map(self.render, node.interfaces)

    @pecan.expose(template='json:', content_type='application/json')
    def put(self, *args):
        """:returns: Collection of JSONized Node objects.
        :http: * 200 (nodes are successfully updated)
               * 400 (invalid nodes data specified)
        """
        if len(args) == 0:
            return self.put_all()

        node_id = args[0]

        interfaces_data = self.checked_data(
            self.validator.validate_structure_and_data, node_id=node_id)
        node_data = {'id': node_id, 'interfaces': interfaces_data}

        objects.Cluster.get_network_manager()._update_attrs(node_data)
        node = self.get_object_or_404(objects.Node, node_id)
        objects.Node.add_pending_change(
            node,
            consts.CLUSTER_CHANGES.interfaces
        )
        return map(self.render, node.interfaces)

    def put_all(self):
        data = self.checked_data(
            self.validator.validate_collection_update
        )

        nodes_updated = []
        for nd in data:
            node = self.collection.single.get_by_meta(nd)

            if not node:
                raise self.http(404, "Can't find node: {0}".format(nd))

            self.collection.single.update(node, nd)
            nodes_updated.append(node.id)

        # we need eagerload everything that is used in render
        nodes = self.collection.filter_by_id_list(
            self.collection.eager_nodes_handlers(None),
            nodes_updated
        )
        return self.collection.to_dict(nodes)


class NodeCollectionNICsController(BaseController):
    """Node collection network interfaces controller
    """

    default_assignment = NodeCollectionNICsDefaultController()

    model = NetworkGroup
    validator = NetAssignmentValidator
    serializer = NodeInterfacesSerializer

    @pecan.expose(template='json:', content_type='application/json')
    def put(self):
        """:returns: Collection of JSONized Node objects.
        :http: * 200 (nodes are successfully updated)
               * 400 (invalid nodes data specified)
        """
        data = self.checked_data(
            self.validator.validate_collection_structure_and_data)
        updated_nodes_ids = []
        for node_data in data:
            node_id = objects.Cluster.get_network_manager(
            )._update_attrs(node_data)
            updated_nodes_ids.append(node_id)
        updated_nodes = db().query(Node).filter(
            Node.id.in_(updated_nodes_ids)
        ).all()
        return [
            {
                "id": n.id,
                "interfaces": map(self.render, n.interfaces)
            } for n in updated_nodes
        ]


class NodesAllocationStatsController(BaseController):
    """Node allocation stats handler
    """

    @pecan.expose(template='json:', content_type='application/json')
    def get_all(self):
        """:returns: Total and unallocated nodes count.
        :http: * 200 (OK)
        """
        unallocated_nodes = db().query(Node).filter_by(cluster_id=None).count()
        total_nodes = \
            db().query(Node).count()
        return {'total': total_nodes,
                'unallocated': unallocated_nodes}


class NodeAllocationController(BaseController):

    stats = NodesAllocationStatsController()


class NodeController(BaseController):
    """Node controller
    """

    agent = NodeAgentController()
    allocation = NodeAllocationController()
    disks = NodeDisksController()
    interfaces = NodeNICsController()
    volumes = NodeVolumesInformationController()

    fields = ('id', 'name', 'meta', 'progress', 'roles', 'pending_roles',
              'status', 'mac', 'fqdn', 'ip', 'manufacturer', 'platform_name',
              'pending_addition', 'pending_deletion', 'os_platform',
              'error_type', 'online', 'cluster', 'uuid')

    single = objects.Node
    collection = objects.NodeCollection
    validator = NodeValidator
    eager = (
        'cluster',
        'nic_interfaces',
        'nic_interfaces.assigned_networks_list',
        'bond_interfaces',
        'bond_interfaces.assigned_networks_list',
        'role_list',
        'pending_role_list'
    )

    @pecan.expose(template='json:', content_type='application/json')
    def get_all(self):
        """May receive cluster_id parameter to filter list
        of nodes

        :returns: Collection of JSONized Node objects.
        :http: * 200 (OK)
        """
        request = pecan.request
        cluster_id = request.params.get("cluster_id", None)
        nodes = self.collection.eager(None, self.eager)

        if cluster_id == '':
            nodes = nodes.filter_by(cluster_id=None)
        elif cluster_id:
            nodes = nodes.filter_by(cluster_id=cluster_id)

        return self.collection.to_list(nodes)

    @pecan.expose(template='json:', content_type='application/json')
    def put(self, *args):
        """:returns: Collection of JSONized Node objects.
        :http: * 200 (nodes are successfully updated)
               * 400 (invalid nodes data specified)
        """
        data = self.checked_data_one_or_many(*args)

        nodes_updated = []
        for nd in data:
            node = self.collection.single.get_by_meta(nd)

            if not node:
                raise self.http(404, "Can't find node: {0}".format(nd))

            self.collection.single.update(node, nd)
            nodes_updated.append(node.id)

        # we need eagerload everything that is used in render
        nodes = self.collection.filter_by_id_list(
            self.collection.eager(None, self.eager),
            nodes_updated
        )
        return self.collection.to_list(nodes)

    @pecan.expose(template='json:', content_type='application/json')
    def delete(self, *args):
        if len(args) == 1:

            node = self.get_object_or_404(self.single, args[0])
            task_manager = NodeDeletionTaskManager(cluster_id=node.cluster_id)
            task = task_manager.execute([node], mclient_remove=False)

            return self.raise_task(task)

        # TODO(pkaminski): web.py does not support parsing of array arguments
        # in the queryset so we specify the input as comma-separated list
        node_ids = self.checked_data(
            validate_method=self.validator.validate_collection_delete,
            data=pecan.request.GET.get('ids', '')
        )

        nodes = self.get_objects_list_or_404(self.single, node_ids)

        task_manager = NodeDeletionTaskManager(cluster_id=nodes[0].cluster_id)
        task = task_manager.execute(nodes)

        return self.raise_task(task)
