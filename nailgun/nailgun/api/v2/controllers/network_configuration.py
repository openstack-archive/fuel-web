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
Controllers dealing with network configurations
"""

import json
import traceback

import pecan

from nailgun.api.v2.controllers.base import BaseController

from nailgun.objects.serializers.network_configuration \
    import NeutronNetworkConfigurationSerializer
from nailgun.objects.serializers.network_configuration \
    import NovaNetworkConfigurationSerializer

from nailgun.api.v1.validators.network \
    import NeutronNetworkConfigurationValidator
from nailgun.api.v1.validators.network \
    import NovaNetworkConfigurationValidator

from nailgun.db import db

from nailgun import objects

from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.objects import Task
from nailgun.task.helpers import TaskHelper
from nailgun.task.manager import CheckNetworksTaskManager
from nailgun.task.manager import VerifyNetworksTaskManager


class ProviderController(BaseController):
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


class NetworkConfigurationVerifyController(ProviderController):
    """Network configuration verify handler base
    """

    @pecan.expose(template='json:', content_type='application/json')
    def put_all(self, cluster_id):
        """:IMPORTANT: this method should be rewritten to be more RESTful

        :returns: JSONized Task object.
        :http: * 202 (network checking task failed)
               * 200 (network verification task started)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        self.check_net_provider(cluster)
        raise self.http(202, self.launch_verify(cluster))

    def launch_verify(self, cluster):
        request = pecan.request
        data = self.validator.validate_networks_update(request.body)

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


class NovaNetworkConfigurationVerifyController(
    NetworkConfigurationVerifyController
):
    """Nova-Network configuration verify handler
    """

    validator = NovaNetworkConfigurationValidator
    provider = "nova_network"


class NeutronNetworkConfigurationVerifyController(
    NetworkConfigurationVerifyController
):
    """Neutron network configuration verify handler
    """

    validator = NeutronNetworkConfigurationValidator
    provider = "neutron"


class NovaNetworkConfigurationController(ProviderController):
    """Network configuration handler
    """

    verify = NovaNetworkConfigurationVerifyController()

    validator = NovaNetworkConfigurationValidator
    serializer = NovaNetworkConfigurationSerializer
    provider = "nova_network"

    @pecan.expose(template='json:', content_type='application/json')
    def get_all(self, cluster_id):
        """:returns: JSONized network configuration for cluster.
        :http: * 200 (OK)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        self.check_net_provider(cluster)
        return self.serializer.serialize_for_cluster(cluster)

    @pecan.expose(template='json:', content_type='application/json')
    def put_all(self, cluster_id):
        """:returns: JSONized Task object.
        :http: * 202 (network checking task created)
               * 404 (cluster not found in db)
        """
        request = pecan.request
        data = json.loads(request.body)
        if data.get("networks"):
            data["networks"] = [
                n for n in data["networks"] if n.get("name") != "fuelweb_admin"
            ]

        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        self.check_net_provider(cluster)

        self.check_if_network_configuration_locked(cluster)

        task_manager = CheckNetworksTaskManager(cluster_id=cluster.id)
        task = task_manager.execute(data)

        if task.status != 'error':
            try:
                if 'networks' in data:
                    self.validator.validate_networks_update(
                        json.dumps(data)
                    )

                if 'dns_nameservers' in data:
                    self.validator.validate_dns_servers_update(
                        json.dumps(data)
                    )

                objects.Cluster.get_network_manager(
                    cluster
                ).update(cluster, data)
            except Exception as exc:
                TaskHelper.set_error(task.uuid, exc)
                logger.error(traceback.format_exc())

        #TODO(enchantner): research this behaviour
        if task.status == 'error':
            db().rollback()
        else:
            db().commit()

        raise self.http(202, Task.to_json(task))


class NeutronNetworkConfigurationController(ProviderController):
    """Neutron Network configuration handler
    """

    verify = NeutronNetworkConfigurationVerifyController()

    validator = NeutronNetworkConfigurationValidator
    serializer = NeutronNetworkConfigurationSerializer
    provider = "neutron"

    @pecan.expose(template='json:', content_type='application/json')
    def get_all(self, cluster_id):
        """:returns: JSONized network configuration for cluster.
        :http: * 200 (OK)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        self.check_net_provider(cluster)
        return self.serializer.serialize_for_cluster(cluster)

    @pecan.expose(template='json:', content_type='application/json')
    def put_all(self, cluster_id):
        request = pecan.request
        data = json.loads(request.body)
        if data.get("networks"):
            data["networks"] = [
                n for n in data["networks"] if n.get("name") != "fuelweb_admin"
            ]
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        self.check_net_provider(cluster)

        self.check_if_network_configuration_locked(cluster)

        task_manager = CheckNetworksTaskManager(cluster_id=cluster.id)
        task = task_manager.execute(data)

        if task.status != 'error':

            try:
                if 'networks' in data:
                    self.validator.validate_networks_update(
                        json.dumps(data)
                    )

                if 'networking_parameters' in data:
                    self.validator.validate_neutron_params(
                        json.dumps(data),
                        cluster_id=cluster_id
                    )

                objects.Cluster.get_network_manager(
                    cluster
                ).update(cluster, data)
            except Exception as exc:
                TaskHelper.set_error(task.uuid, exc)
                logger.error(traceback.format_exc())

        #TODO(enchantner): research this behaviour
        if task.status == 'error':
            db().rollback()
        else:
            db().commit()

        raise self.http(202, Task.to_json(task))


class NetworkConfigurationController(BaseController):

    nova_network = NovaNetworkConfigurationController()
    neutron = NeutronNetworkConfigurationController()
