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

import six

from novaclient import client as nova_client

from nailgun import consts
from nailgun.logger import logger
from nailgun.network import manager
from nailgun import objects
from nailgun.settings import settings

from nailgun.statistics import utils


class ClientProvider(object):
    """Initialize clients for OpenStack components
    and expose them as attributes
    """

    def __init__(self, cluster):
        self.cluster = cluster
        self._nova = None
        self._credentials = None

    @property
    def nova(self):
        if self._nova is None:
            self._nova = nova_client.Client(
                settings.OPENSTACK_API_VERSION["nova"],
                *self.credentials,
                service_type=consts.NOVA_SERVICE_TYPE.compute
            )

        return self._nova

    @property
    def credentials(self):
        if self._credentials is None:
            access_data = objects.Cluster.get_creds(self.cluster)

            os_user = access_data["user"]["value"]
            os_password = access_data["password"]["value"]
            os_tenant = access_data["tenant"]["value"]

            auth_host = self._get_host_for_auth()
            auth_url = "http://{0}:{1}/v2.0/".format(auth_host,
                                                     settings.AUTH_PORT)

            self._credentials = (os_user, os_password, os_tenant, auth_url)

        return self._credentials

    def _get_host_for_auth(self):
        return manager.NetworkManager._get_ip_by_network_name(
            utils.get_online_controller(self.cluster),
            consts.NETWORKS.management
        ).ip_addr


class OpenStackInfoCollector(object):
    """Introduce interface for collecting
    info from OpenStack installation

    Side effect: set 'http_proxy' environment variable
    for the time of request to OpenStack components
    """

    def __init__(self, cluster, client_provider):
        self.cluster = cluster
        self.client_provider = client_provider

    @property
    def proxy(self):
        proxy_host = utils.get_online_controller(self.cluster).ip
        proxy_port = settings.OPENSTACK_INFO_COLLECTOR_PROXY_PORT
        proxy = "http://{0}:{1}".format(proxy_host, proxy_port)

        return proxy

    def get_vm_info(self):
        vm_info = {}

        with utils.set_proxy(self.proxy):
            try:
                servers = self.client_provider.nova.servers.list()

                instances_info = []
                for serv in servers:
                    inst_details = {}

                    inst_details["id"] = getattr(serv, "id", None)
                    inst_details["status"] = getattr(serv, "status", None)
                    inst_details["host_id"] = getattr(serv, "hostId", None)
                    inst_details["tenant_id"] = getattr(serv, "tenant_id",
                                                        None)
                    inst_details["created_at"] = getattr(serv, "created", None)
                    inst_details["power_state"] = \
                        getattr(serv, "OS-EXT-STS:power_state", None)
                    inst_details["flavor_id"] = \
                        getattr(serv, "flavor", {}).get("id")
                    inst_details["image_id"] = \
                        getattr(serv, "image", {}).get("id")

                    instances_info.append(inst_details)

                vm_info["vms_details"] = instances_info
            except Exception as e:
                logger.exception("Error while collecting workloads for VMs. "
                                 "Details: {0}".format(six.text_type(e)))

        return vm_info
