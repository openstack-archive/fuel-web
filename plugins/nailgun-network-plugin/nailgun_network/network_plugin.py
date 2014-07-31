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
Handlers dealing with network configurations
"""

import traceback
from datetime import datetime

import six
import web
from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.objects.serializers.network_configuration \
    import NeutronNetworkConfigurationSerializer
from nailgun.objects.serializers.network_configuration \
    import NovaNetworkConfigurationSerializer
from nailgun.api.v1.validators.network \
    import NeutronNetworkConfigurationValidator
from nailgun.api.v1.validators.network \
    import NovaNetworkConfigurationValidator
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.objects import Task
from nailgun.openstack.common import jsonutils
from nailgun.task.manager import CheckNetworksTaskManager
from nailgun.task.manager import VerifyNetworksTaskManager
from nailgun.utils import dict_merge
from nailgun.api.v1.handlers.base import CollectionHandler
from nailgun.api.v1.handlers.base import content_json
from nailgun.api.v1.handlers.base import SingleHandler
from nailgun.api.v1.validators.node import NodeValidator
from nailgun import objects
from nailgun.db import db
from nailgun import notifier

from nailgun.plugins import classes as plugin_classes
from nailgun.nailgun.plugins.classes.astute import AstutePlugin
import serializer


class NailgunNetworkPlugin(plugin_classes.RESTAPIPlugin,
                           AstutePlugin):

    __plugin_name__ = "network_plugin"

    @classmethod
    def get_urls(cls):
        cls.urls = (
        )
        return cls.urls

    def process_node_attrs(self, node, node_attrs):
        node_attrs.update(
            serializer.get_node_attrs(node))
        return node_attrs

    def process_cluster_attrs(self, cluster, attrs):
        attrs = dict_merge(
            attrs,
            serializer.get_cluster_attrs(cluster, attrs))
        return attrs

    def process_cluster_ha_attrs(self, cluster, attrs):
        assign_vip_attrs = serializer.get_assign_vip(cluster)
        attrs.update(assign_vip_attrs)
        return attrs

class ProviderHandler(BaseHandler):
    """Base class for network configuration handlers
    """

    def check_net_provider(self, cluster):
        if cluster.net_provider != self.provider:
            raise self.http(
                400, u"Wrong net provider - environment uses '{0}'".format(
                    cluster.net_provider
                )
            )

    def check_if_network_configuration_locked(self, cluster):
        if cluster.is_locked:
            raise self.http(403, "Network configuration can't be changed "
                                 "after, or in deploy.")


class NovaNetworkConfigurationHandler(ProviderHandler):
    """Network configuration handler
    """

    validator = NovaNetworkConfigurationValidator
    serializer = NovaNetworkConfigurationSerializer
    provider = "nova_network"

    @content_json
    def GET(self, cluster_id):
        """:returns: JSONized network configuration for cluster.
        :http: * 200 (OK)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(Cluster, cluster_id)
        self.check_net_provider(cluster)
        return self.serializer.serialize_for_cluster(cluster)

    @content_json
    def PUT(self, cluster_id):
        """:returns: JSONized Task object.
        :http: * 202 (network checking task created)
               * 404 (cluster not found in db)
        """
        data = jsonutils.loads(web.data())
        if data.get("networks"):
            data["networks"] = [
                n for n in data["networks"] if n.get("name") != "fuelweb_admin"
            ]

        cluster = self.get_object_or_404(Cluster, cluster_id)
        self.check_net_provider(cluster)

        self.check_if_network_configuration_locked(cluster)

        task_manager = CheckNetworksTaskManager(cluster_id=cluster.id)
        task = task_manager.execute(data)

        if task.status != 'error':
            try:
                if 'networks' in data:
                    self.validator.validate_networks_update(
                        jsonutils.dumps(data)
                    )

                if 'dns_nameservers' in data:
                    self.validator.validate_dns_servers_update(
                        jsonutils.dumps(data)
                    )

                objects.Cluster.get_network_manager(
                    cluster
                ).update(cluster, data)
            except Exception as exc:
                # set task status to error and update its corresponding data
                data = {'status': 'error',
                        'progress': 100,
                        'message': six.text_type(exc)}
                objects.Task.update(task, data)

                logger.error(traceback.format_exc())

        #TODO(enchantner): research this behaviour
        if task.status == 'error':
            db().rollback()
        else:
            db().commit()

        raise self.http(202, Task.to_json(task))


class NeutronNetworkConfigurationHandler(ProviderHandler):
    """Neutron Network configuration handler
    """

    validator = NeutronNetworkConfigurationValidator
    serializer = NeutronNetworkConfigurationSerializer
    provider = "neutron"

    @content_json
    def GET(self, cluster_id):
        """:returns: JSONized network configuration for cluster.
        :http: * 200 (OK)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(Cluster, cluster_id)
        self.check_net_provider(cluster)
        return self.serializer.serialize_for_cluster(cluster)

    @content_json
    def PUT(self, cluster_id):
        data = jsonutils.loads(web.data())
        if data.get("networks"):
            data["networks"] = [
                n for n in data["networks"] if n.get("name") != "fuelweb_admin"
            ]
        cluster = self.get_object_or_404(Cluster, cluster_id)
        self.check_net_provider(cluster)

        self.check_if_network_configuration_locked(cluster)

        task_manager = CheckNetworksTaskManager(cluster_id=cluster.id)
        task = task_manager.execute(data)

        if task.status != 'error':

            try:
                if 'networks' in data:
                    self.validator.validate_networks_update(
                        jsonutils.dumps(data)
                    )

                if 'networking_parameters' in data:
                    self.validator.validate_neutron_params(
                        jsonutils.dumps(data),
                        cluster_id=cluster_id
                    )

                objects.Cluster.get_network_manager(
                    cluster
                ).update(cluster, data)
            except Exception as exc:
                # set task status to error and update its corresponding data
                data = {'status': 'error',
                        'progress': 100,
                        'message': six.text_type(exc)}
                objects.Task.update(task, data)

                logger.error(traceback.format_exc())

        #TODO(enchantner): research this behaviour
        if task.status == 'error':
            db().rollback()
        else:
            db().commit()

        raise self.http(202, Task.to_json(task))


class NetworkConfigurationVerifyHandler(ProviderHandler):
    """Network configuration verify handler base
    """

    @content_json
    def PUT(self, cluster_id):
        """:IMPORTANT: this method should be rewritten to be more RESTful

        :returns: JSONized Task object.
        :http: * 202 (network checking task failed)
               * 200 (network verification task started)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(Cluster, cluster_id)
        self.check_net_provider(cluster)
        raise self.http(202, self.launch_verify(cluster))

    def launch_verify(self, cluster):
        data = self.validator.validate_networks_update(web.data())

        data["networks"] = [
            n for n in data["networks"] if n.get("name") != "fuelweb_admin"
        ]

        vlan_ids = [{
                    'name': n['name'],
                    'vlans': objects.Cluster.get_network_manager(
                        cluster
                    ).generate_vlan_ids_list(
                        data, cluster, n)
                    } for n in data['networks']]

        task_manager = VerifyNetworksTaskManager(cluster_id=cluster.id)
        try:
            task = task_manager.execute(data, vlan_ids)
        except errors.CantRemoveOldVerificationTask:
            raise self.http(400, "You cannot delete running task manually")
        return Task.to_json(task)


class NovaNetworkConfigurationVerifyHandler(NetworkConfigurationVerifyHandler):
    """Nova-Network configuration verify handler
    """

    validator = NovaNetworkConfigurationValidator
    provider = "nova_network"


class NeutronNetworkConfigurationVerifyHandler(
        NetworkConfigurationVerifyHandler):
    """Neutron network configuration verify handler
    """

    validator = NeutronNetworkConfigurationValidator
    provider = "neutron"


class NodeHandler(SingleHandler):

    single = objects.Node
    validator = NodeValidator


class NodeCollectionHandler(CollectionHandler):
    """Node collection handler
    """

    fields = ('id', 'name', 'meta', 'progress', 'roles', 'pending_roles',
              'status', 'mac', 'fqdn', 'ip', 'manufacturer', 'platform_name',
              'pending_addition', 'pending_deletion', 'os_platform',
              'error_type', 'online', 'cluster', 'uuid', 'network_data')

    validator = NodeValidator
    collection = objects.NodeCollection

    @content_json
    def GET(self):
        """May receive cluster_id parameter to filter list
        of nodes

        :returns: Collection of JSONized Node objects.
        :http: * 200 (OK)
        """
        cluster_id = web.input(cluster_id=None).cluster_id
        nodes = self.collection.eager_nodes_handlers(None)

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
        return self.collection.to_json(nodes)


class NodeAgentHandler(BaseHandler):

    collection = objects.NodeCollection
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
            data=u'[{0}]'.format(web.data()))[0]

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
