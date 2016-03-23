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

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import content

from nailgun.objects.serializers.network_configuration \
    import NeutronNetworkConfigurationSerializer
from nailgun.objects.serializers.network_configuration \
    import NovaNetworkConfigurationSerializer

from nailgun.api.v1.validators.network import NetworkConfigurationValidator
from nailgun.api.v1.validators.network import NetworkTemplateValidator
from nailgun.api.v1.validators.network \
    import NeutronNetworkConfigurationValidator
from nailgun.api.v1.validators.network \
    import NovaNetworkConfigurationValidator

from nailgun import consts
from nailgun import objects

from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.task.manager import CheckNetworksTaskManager
from nailgun.task.manager import UpdateDnsmasqTaskManager
from nailgun.task.manager import VerifyNetworksTaskManager


class ProviderHandler(BaseHandler):
    """Base class for network configuration handlers"""

    provider = None

    def check_net_provider(self, cluster):
        if cluster.net_provider != self.provider:
            raise self.http(
                400, u"Wrong net provider - environment uses '{0}'".format(
                    cluster.net_provider
                )
            )

    def check_if_network_configuration_locked(self, cluster):
        if objects.Cluster.is_network_modification_locked(cluster):
            raise self.http(403, "Network configuration cannot be changed "
                                 "during deployment and after upgrade.")

    def _get_cluster_and_validated_network_data(self, cluster_id):
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        self.check_net_provider(cluster)

        data = self.checked_data(
            self.validator.validate_networks_data,
            cluster=cluster, networks_required=False)
        return cluster, data

    @content
    def GET(self, cluster_id):
        """:returns: JSONized network configuration for cluster.

        :http: * 200 (OK)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        self.check_net_provider(cluster)

        try:
            # there are a plenty of reasons why serializer could throw
            # an exception. usually that means we don't handle properly
            # some corner cases, and it should be fixed. in order
            # to simplify troubleshootng, let's print traceback to log.
            return self.serializer.serialize_for_cluster(cluster)
        except Exception:
            logger.exception('Serialization failed')
            raise

    @content
    def PUT(self, cluster_id):
        """:returns: JSONized network configuration for cluster.

        :http: * 200 (OK)
               * 400 (data validation or some of tasks failed)
               * 404 (cluster not found in db)
               * 409 (previous dsnmasq setup is not finished yet)
        """
        cluster, data = self._get_cluster_and_validated_network_data(
            cluster_id)

        self.check_if_network_configuration_locked(cluster)

        task_manager = CheckNetworksTaskManager(cluster_id=cluster.id)
        task = task_manager.execute(data)

        if task.status == consts.TASK_STATUSES.error:
            raise self.http(400, task.message, err_list=task.result)

        nm = objects.Cluster.get_network_manager(cluster)
        admin_nets = nm.get_admin_networks()
        nm.update(cluster, data)

        network_config = self.serializer.serialize_for_cluster(cluster)

        if admin_nets != nm.get_admin_networks():
            try:
                task = UpdateDnsmasqTaskManager().execute()
            except errors.TaskAlreadyRunning:
                raise self.http(409, errors.UpdateDnsmasqTaskIsRunning.message)
            if task.status == consts.TASK_STATUSES.error:
                raise self.http(400, task.message)

        return network_config


class NovaNetworkConfigurationHandler(ProviderHandler):
    """Network configuration handler"""

    validator = NovaNetworkConfigurationValidator
    serializer = NovaNetworkConfigurationSerializer
    provider = consts.CLUSTER_NET_PROVIDERS.nova_network


class NeutronNetworkConfigurationHandler(ProviderHandler):
    """Neutron Network configuration handler"""

    validator = NeutronNetworkConfigurationValidator
    serializer = NeutronNetworkConfigurationSerializer
    provider = consts.CLUSTER_NET_PROVIDERS.neutron


class TemplateNetworkConfigurationHandler(BaseHandler):
    """Neutron Network configuration handler"""
    validator = NetworkTemplateValidator

    def check_if_template_modification_locked(self, cluster):
        if objects.Cluster.is_network_modification_locked(cluster):
            raise self.http(403, "Network template cannot be changed "
                                 "during deployment and after upgrade.")

    @content
    def GET(self, cluster_id):
        """:returns: network template for cluster (json format)

        :http: * 200 (OK)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        return cluster.network_config.configuration_template

    @content
    def PUT(self, cluster_id):
        """:returns: {}

        :http: * 200 (OK)
               * 400 (invalid object data specified)
               * 403 (change of configuration is forbidden)
               * 404 (cluster not found in db)
        """
        template = self.checked_data()

        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        self.check_if_template_modification_locked(cluster)
        objects.Cluster.set_network_template(cluster, template)
        raise self.http(200, template)

    def DELETE(self, cluster_id):
        """:returns: {}

        :http: * 204 (object successfully deleted)
               * 403 (change of configuration is forbidden)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        self.check_if_template_modification_locked(cluster)
        objects.Cluster.set_network_template(cluster, None)
        raise self.http(204)


class NetworkConfigurationVerifyHandler(ProviderHandler):
    """Network configuration verify handler base"""

    validator = NetworkConfigurationValidator

    @content
    def PUT(self, cluster_id):
        """:IMPORTANT: this method should be rewritten to be more RESTful

        :returns: JSONized Task object.
        :http: * 200 (network verification task finished/has error)
               * 202 (network verification task running)
               * 400 (data validation failed)
               * 404 (cluster not found in db)
        """
        cluster, data = self._get_cluster_and_validated_network_data(
            cluster_id)

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
        except errors.OutOfIPs as err:
            raise self.http(400, err.message)

        self.raise_task(task)


class NovaNetworkConfigurationVerifyHandler(NetworkConfigurationVerifyHandler):
    """Nova-Network configuration verify handler"""

    validator = NovaNetworkConfigurationValidator
    provider = consts.CLUSTER_NET_PROVIDERS.nova_network


class NeutronNetworkConfigurationVerifyHandler(
        NetworkConfigurationVerifyHandler):
    """Neutron network configuration verify handler"""

    validator = NeutronNetworkConfigurationValidator
    provider = consts.CLUSTER_NET_PROVIDERS.neutron


class NetworkAttributesDeployedHandler(BaseHandler):
    """Cluster deployed network attributes handler"""

    @content
    def GET(self, cluster_id):
        """:returns: JSONized deployed Cluster network configuration.

        :http: * 200 (OK)
               * 404 (cluster not found in db)
               * 404 (cluster does not have deployed configuration)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        attrs = objects.Transaction.get_network_settings(
            objects.TransactionCollection.get_last_succeed_run(cluster)
        )
        if not attrs:
            raise self.http(
                404, "Cluster does not have deployed configuration!"
            )
        return attrs
