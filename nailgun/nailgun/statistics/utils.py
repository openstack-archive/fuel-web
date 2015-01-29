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

import os
import random
import six

from contextlib import contextmanager

from novaclient import client as nova_client

from nailgun import consts
from nailgun.logger import logger
from nailgun.network import manager
from nailgun import objects
from nailgun.settings import settings


collected_components_attrs = {
    "vm": {
        "attr_names": {
            "id": ["id"],
            "status": ["status"],
            "tenant_id": ["tenant_id"],
            "host_id": ["hostId"],
            "created_at": ["created"],
            "power_state": ["OS-EXT-STS:power_state"],
            "flavor_id": ["flavor", "id"],
            "image_id": ["image", "id"]
        },
        "resource_manager_path": ["nova", "servers"]
    },
}


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

            auth_host = _get_host_for_auth(self.cluster)
            auth_url = "http://{0}:{1}/{2}/".format(
                auth_host, settings.AUTH_PORT,
                settings.OPENSTACK_API_VERSION["keystone"])

            self._credentials = (os_user, os_password, os_tenant, auth_url)

        return self._credentials


def _get_host_for_auth(cluster):
    return manager.NetworkManager._get_ip_by_network_name(
        _get_online_controller(cluster),
        consts.NETWORKS.management
    ).ip_addr


def get_proxy_for_cluster(cluster):
    proxy_host = _get_online_controller(cluster).ip
    proxy_port = settings.OPENSTACK_INFO_COLLECTOR_PROXY_PORT
    proxy = "http://{0}:{1}".format(proxy_host, proxy_port)

    return proxy


def _get_online_controller(cluster):
    return filter(
        lambda node: (
            "controller" in node.roles and node.online is True),
        cluster.nodes
    )[0]


def get_info_from_os_resource_manager(client_provider, resource_name):
    resource = collected_components_attrs[resource_name]
    resource_manager = _get_nested_attr(
        client_provider,
        resource["resource_manager_path"]
    )
    instances_list = resource_manager.list()
    resource_info = []

    for inst in instances_list:
        inst_details = {}

        for attr_name, attr_path in six.iteritems(resource["attr_names"]):
            obj_dict = inst.to_dict()
            inst_details[attr_name] = _get_value_from_nested_dict(
                obj_dict, attr_path
            )

        resource_info.append(inst_details)

    return resource_info


def _get_value_from_nested_dict(obj_dict, key_path):
    value = obj_dict.get(key_path[0])

    if isinstance(value, dict):
        return _get_value_from_nested_dict(value, key_path[1:])

    return value


def _get_nested_attr(obj, attr_path):
    if attr_path:
        attr_name = attr_path.pop(0)
        attr_value = getattr(obj, attr_name)

        nested_value = _get_nested_attr(attr_value, attr_path)

        if nested_value:
            return nested_value
        else:
            return attr_value
    else:
        return None


@contextmanager
def set_proxy(proxy):
    """Replace http_proxy environment variable for the scope
    of context execution. After exit from context old proxy value
    (if any) is restored

    :param proxy: - proxy url
    """
    proxy_old_value = None

    if os.environ.get("http_proxy"):
        proxy_old_value = os.environ["http_proxy"]
        logger.warning("http_proxy variable is already set with "
                       "value: {0}. Change to {1}. Old value "
                       "will be restored after exit from script's "
                       "execution context"
                       .format(proxy_old_value, proxy))

    os.environ["http_proxy"] = proxy

    try:
        yield
    except Exception as e:
        logger.exception("Error while talking to proxy. Details: {0}"
                         .format(six.text_type(e)))
    finally:
        if proxy_old_value:
            logger.info("Restoring old value for http_proxy")
            os.environ["http_proxy"] = proxy_old_value
        else:
            logger.info("Deleting set http_proxy environment variable")
            del os.environ["http_proxy"]


def dithered(medium, interval=(0.9, 1.1)):
    return random.randint(int(medium * interval[0]), int(medium * interval[1]))
