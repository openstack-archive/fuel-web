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
Handlers dealing with nodes
"""

from datetime import datetime
import traceback

from ipaddr import IPAddress
from ipaddr import IPNetwork

import web

from nailgun.api.handlers.base import BaseHandler
from nailgun.api.handlers.base import CollectionHandler
from nailgun.api.handlers.base import content_json
from nailgun.api.handlers.base import SingleHandler
from nailgun.api.serializers.node import NodeInterfacesSerializer
from nailgun.api.validators.network import NetAssignmentValidator
from nailgun.api.validators.node import NodeValidator

from nailgun import objects

from nailgun.db import db
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import NodeAttributes
from nailgun.db.sqlalchemy.models import NodeNICInterface

from nailgun.logger import logger
from nailgun.network.manager import NetworkManager
from nailgun import notifier


class NodeHandler(SingleHandler):
    single = objects.Node
    validator = NodeValidator


class NodeCollectionHandler(CollectionHandler):
    """Node collection handler
    """

    fields = ('id', 'name', 'meta', 'progress', 'roles', 'pending_roles',
              'status', 'mac', 'fqdn', 'ip', 'manufacturer', 'platform_name',
              'pending_addition', 'pending_deletion', 'os_platform',
              'error_type', 'online', 'cluster', 'group_id', 'uuid')

    validator = NodeValidator
    collection = objects.NodeCollection
    eager = (
        'cluster',
        'nic_interfaces',
        'nic_interfaces.assigned_networks_list',
        'bond_interfaces',
        'bond_interfaces.assigned_networks_list',
        'role_list',
        'pending_role_list'
    )

    @content_json
    def GET(self):
        """May receive cluster_id parameter to filter list
        of nodes

        :returns: Collection of JSONized Node objects.
        :http: * 200 (OK)
        """
        cluster_id = web.input(cluster_id=None).cluster_id
        nodes = self.collection.eager(None, self.eager)

        if cluster_id == '':
            nodes = nodes.filter_by(cluster_id=None)
        elif cluster_id:
            nodes = nodes.filter_by(cluster_id=cluster_id)

        return self.collection.to_json(nodes)

    @content_json
    def PUT(self):
        """:returns: Collection of JSONized Node objects.
        :http: * 200 (nodes are successfully updated)
               * 400 (invalid nodes data specified)
        """
        data = self.checked_data(
            self.validator.validate_collection_update
        )

        nodes_updated = []
        for nd in data:
            node = self.collection.single.get_by_mac_or_uid(
                mac=nd.get("mac"),
                node_uid=nd.get("id")
            )
            if not node:
                can_search_by_ifaces = all([
                    nd.get("mac"),
                    nd.get("meta"),
                    nd["meta"].get("interfaces")
                ])
                if can_search_by_ifaces:
                    node = self.collection.single.search_by_interfaces(
                        nd["meta"]["interfaces"]
                    )

            if not node:
                raise self.http(
                    404,
                    "Can't find node: {0}".format(nd)
                )

            self.collection.single.update(node, nd)
            nodes_updated.append(node.id)

        # we need eagerload everything that is used in render
        nodes = self.collection.get_by_id_list(
            self.collection.eager(None, self.eager),
            nodes_updated
        )
        return self.collection.to_json(nodes)


class NodeAgentHandler(BaseHandler):

    validator = NodeValidator

    @content_json
    def PUT(self):
        """:returns: node id.
        :http: * 200 (node are successfully updated)
               * 304 (node data not changed since last request)
               * 400 (invalid nodes data specified)
               * 404 (node not found)
        """
        nd = self.checked_data(
            self.validator.validate_collection_update,
            data=u'[{0}]'.format(web.data())
        )[0]

        q = db().query(Node)
        if nd.get("mac"):
            node = (
                q.filter_by(mac=nd["mac"]).first()
                or self.validator.validate_existent_node_mac_update(nd)
            )
        else:
            node = q.get(nd["id"])

        if not node:
            raise self.http(404)

        node.timestamp = datetime.now()

        if node.group_id is None:
            admin_ngs = db().query(NetworkGroup).filter_by(
                name="fuelweb_admin")
            ip = IPAddress(node.ip)
            for ng in admin_ngs:
                if ip in IPNetwork(ng.cidr):
                    node.group_id = ng.group_id
                    if node.error_type == 'discover':
                        node.error_type = None
                        node.error_msg = None
                        notifier.notify(
                            "discover",
                            (
                                u"Node '{0}' rejoined with group_id '{1}'"
                            ).format(
                                node.name or node.mac, node.group_id
                            ),
                            node_id=node.id
                        )
                        node.status = 'rollback'
                    break
            if node.group_id is None and node.error_type is None:
                msg = (
                    u"Failed to match node '{0}' with group_id. Add "
                    "fuelweb_admin NetworkGroup to match '{1}'"
                ).format(
                    node.name or node.mac,
                    node.ip
                )
                logger.warning(msg)
                notifier.notify("error", msg, node_id=node.id)

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

        for key, value in nd.iteritems():
            if (
                (key, value) == ("status", "discover")
                and node.status in ('provisioning', 'error')
            ):
                # We don't update provisioning and error back to discover
                logger.debug(
                    u"Node {0} has provisioning or error status - "
                    u"status not updated by agent".format(
                        node.human_readable_name
                    )
                )
                continue
            if key == "meta":
                node.update_meta(value)
            # don't update node ID
            elif key != "id":
                setattr(node, key, value)
        db().flush()
        if not node.attributes:
            node.attributes = NodeAttributes()
            db().flush()
        if not node.attributes.volumes:
            node.attributes.volumes = node.volume_manager.gen_volumes_info()
            db().flush()
        if node.status not in ('provisioning', 'deploying'):
            variants = (
                "disks" in node.meta and len(node.meta["disks"]) != len(
                    filter(
                        lambda d: d["type"] == "disk",
                        node.attributes.volumes
                    )
                ),
            )
            if any(variants):
                try:
                    node.attributes.volumes = (
                        node.volume_manager.gen_volumes_info()
                    )
                    if node.cluster:
                        objects.Cluster.add_pending_changes(
                            node.cluster,
                            "disks",
                            node_id=node.id
                        )
                except Exception as exc:
                    msg = (
                        "Failed to generate volumes info for node '{0}': '{1}'"
                    ).format(
                        node.human_readable_name,
                        str(exc) or "see logs for details"
                    )
                    logger.warning(traceback.format_exc())
                    notifier.notify("error", msg, node_id=node.id)

            db().flush()

        NetworkManager.update_interfaces_info(node)

        return {"id": node.id}


class NodeNICsHandler(BaseHandler):
    """Node network interfaces handler
    """

    model = NodeNICInterface
    validator = NetAssignmentValidator
    serializer = NodeInterfacesSerializer

    @content_json
    def GET(self, node_id):
        """:returns: Collection of JSONized Node interfaces.
        :http: * 200 (OK)
               * 404 (node not found in db)
        """
        node = self.get_object_or_404(Node, node_id)
        return map(self.render, node.interfaces)

    @content_json
    def PUT(self, node_id):
        """:returns: Collection of JSONized Node objects.
        :http: * 200 (nodes are successfully updated)
               * 400 (invalid nodes data specified)
        """
        interfaces_data = self.checked_data(
            self.validator.validate_structure_and_data, node_id=node_id)
        node_data = {'id': node_id, 'interfaces': interfaces_data}

        NetworkManager._update_attrs(node_data)
        node = self.get_object_or_404(Node, node_id)
        return map(self.render, node.interfaces)


class NodeCollectionNICsHandler(BaseHandler):
    """Node collection network interfaces handler
    """

    model = NetworkGroup
    validator = NetAssignmentValidator
    serializer = NodeInterfacesSerializer

    @content_json
    def PUT(self):
        """:returns: Collection of JSONized Node objects.
        :http: * 200 (nodes are successfully updated)
               * 400 (invalid nodes data specified)
        """
        data = self.checked_data(
            self.validator.validate_collection_structure_and_data)
        updated_nodes_ids = []
        for node_data in data:
            node_id = NetworkManager._update_attrs(node_data)
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


class NodeNICsDefaultHandler(BaseHandler):
    """Node default network interfaces handler
    """

    @content_json
    def GET(self, node_id):
        """:returns: Collection of default JSONized interfaces for node.
        :http: * 200 (OK)
               * 404 (node not found in db)
        """
        node = self.get_object_or_404(Node, node_id)
        default_nets = self.get_default(node)
        return default_nets

    def get_default(self, node):
        if node.cluster:
            return node.cluster.network_manager.\
                get_default_networks_assignment(node)


class NodeCollectionNICsDefaultHandler(NodeNICsDefaultHandler):
    """Node collection default network interfaces handler
    """

    validator = NetAssignmentValidator

    @content_json
    def GET(self):
        """May receive cluster_id parameter to filter list
        of nodes

        :returns: Collection of JSONized Nodes interfaces.
        :http: * 200 (OK)
               * 404 (node not found in db)
        """
        cluster_id = web.input(cluster_id=None).cluster_id
        if cluster_id == '':
            nodes = self.get_object_or_404(Node, cluster_id=None)
        elif cluster_id:
            nodes = self.get_object_or_404(
                Node,
                cluster_id=cluster_id
            )
        else:
            nodes = self.get_object_or_404(Node)
        def_net_nodes = []
        for node in nodes:
            rendered_node = self.get_default(self.render(node))
            def_net_nodes.append(rendered_node)
        return map(self.render, nodes)


class NodesAllocationStatsHandler(BaseHandler):
    """Node allocation stats handler
    """

    @content_json
    def GET(self):
        """:returns: Total and unallocated nodes count.
        :http: * 200 (OK)
        """
        unallocated_nodes = db().query(Node).filter_by(cluster_id=None).count()
        total_nodes = \
            db().query(Node).count()
        return {'total': total_nodes,
                'unallocated': unallocated_nodes}
