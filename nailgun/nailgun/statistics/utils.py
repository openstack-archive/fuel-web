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

from cinderclient import client as cinder_client
from keystoneclient import discover as keystone_discover
from keystoneclient.v2_0 import client as keystone_client_v2
from keystoneclient.v3 import client as keystone_client_v3
from novaclient import client as nova_client

from nailgun import consts
from nailgun.db import db
from nailgun.logger import logger
from nailgun.network import manager
from nailgun import objects
from nailgun.settings import settings
from nailgun.statistics.oswl_resources_description import resources_description


class ClientProvider(object):
    """Initialize clients for OpenStack components
    and expose them as attributes
    """

    clients_version_attr_path = {
        "nova": ["client", "version"],
        "cinder": ["client", "version"],
        "keystone": ["version"]
    }

    def __init__(self, cluster):
        self.cluster = cluster
        self._nova = None
        self._cinder = None
        self._keystone = None
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
    def cinder(self):
        if self._cinder is None:
            self._cinder = cinder_client.Client(
                settings.OPENSTACK_API_VERSION["cinder"],
                *self.credentials
            )

        return self._cinder

    @property
    def keystone(self):
        if self._keystone is None:
            # kwargs are universal for v2 and v3 versions of
            # keystone client that are different only in accepting
            # of tenant/project keyword name
            auth_kwargs = {
                "username": self.credentials[0],
                "password": self.credentials[1],
                "tenant_name": self.credentials[2],
                "project_name": self.credentials[2],
                "auth_url": self.credentials[3]
            }
            self._keystone = self._get_keystone_client(auth_kwargs)

        return self._keystone

    def _get_keystone_client(self, auth_creds):
        """Instantiate client based on returned from keystone
        server version data.

        :param auth_creds: credentials for authentication which also are
        parameters for client's instance initialization
        :returns: instance of keystone client of appropriate version
        :raises: exception if response from server contains version other than
        2.x and 3.x
        """
        discover = keystone_discover.Discover(**auth_creds)

        for version_data in discover.version_data():
            version = version_data["version"][0]
            if version <= 2:
                return keystone_client_v2.Client(**auth_creds)
            elif version == 3:
                return keystone_client_v3.Client(**auth_creds)

        raise Exception("Failed to discover keystone version "
                        "for auth_url {0}".format(
                            auth_creds.get("auth_url"))
                        )

    @property
    def credentials(self):
        if self._credentials is None:
            access_data = objects.Cluster.get_editable_attributes(
                self.cluster
            )['editable']['workloads_collector']

            os_user = access_data["username"]["value"]
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


def _get_data_from_resource_manager(resource_manager, attr_names_mapping,
                                    additional_display_options):
    data = []

    display_options = {}
    display_options.update(additional_display_options)

    instances_list = resource_manager.list(**display_options)
    for inst in instances_list:
        inst_details = {}

        for attr_name, attr_path in six.iteritems(attr_names_mapping):
            obj_dict = \
                inst.to_dict() if hasattr(inst, "to_dict") else inst.__dict__
            inst_details[attr_name] = _get_value_from_nested_dict(
                obj_dict, attr_path
            )

        data.append(inst_details)

    return data


def get_info_from_os_resource_manager(client_provider, resource_name):
    """Utilize clients provided by client_provider instance to retrieve
    data for resource_name, description of which is stored in
    resources_description data structure.

    :param client_provider: objects that provides instances of openstack
    clients as its attributes
    :param resource_name: string that contains name of resource for which
    info should be collected from installation
    :returns: data that store collected info
    """
    resource_description = resources_description[resource_name]

    client_name = resource_description["retrieved_from_component"]
    client_inst = getattr(client_provider, client_name)

    client_api_version = _get_nested_attr(
        client_inst,
        client_provider.clients_version_attr_path[client_name]
    )

    matched_api = \
        resource_description["supported_api_versions"][client_api_version]

    resource_manager_name = matched_api["resource_manager_name"]
    resource_manager = getattr(client_inst, resource_manager_name)

    attributes_names_mapping = matched_api["retrieved_attr_names_mapping"]

    additional_display_options = \
        matched_api.get("additional_display_options", {})

    resource_info = _get_data_from_resource_manager(
        resource_manager,
        attributes_names_mapping,
        additional_display_options
    )

    return resource_info


def _get_value_from_nested_dict(obj_dict, key_path):
    if not isinstance(obj_dict, dict) or not key_path:
        return None

    value = obj_dict.get(key_path[0])

    if isinstance(value, dict):
        return _get_value_from_nested_dict(value, key_path[1:])

    return value


def _get_nested_attr(obj, attr_path):
    # prevent from error in case of empty list and
    # None object
    if not all([obj, attr_path]):
        return None

    attr_name = attr_path[0]
    attr_value = getattr(obj, attr_name, None)

    # stop recursion as we already are on last level of attributes nesting
    if len(attr_path) == 1:
        return attr_value

    return _get_nested_attr(attr_value, attr_path[1:])


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


def delete_expired_oswl_entries():
    try:
        deleted_rows_count = \
            objects.OpenStackWorkloadStatsCollection.clean_expired_entries()

        if deleted_rows_count == 0:
            logger.info("There are no expired OSWL entries in db.")

        db().commit()

        logger.info("Expired OSWL entries are "
                    "successfully cleaned from db")

    except Exception as e:
        logger.exception("Exception while cleaning oswls entries from "
                         "db. Details: {0}".format(six.text_type(e)))
    finally:
        db.remove()
