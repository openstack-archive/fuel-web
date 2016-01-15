#    Copyright 2015 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import logging
import six

from cinderclient import client as cinder_client
from keystoneclient import discover as keystone_discover
from keystoneclient.v2_0 import client as keystone_client_v2
from keystoneclient.v3 import client as keystone_client_v3
from novaclient import client as nova_client

from nailgun import consts
from nailgun.db import db
from nailgun import objects
from nailgun.settings import settings
from nailgun.statistics.oswl.resources_description \
    import resources_description
from nailgun.statistics import utils


logger = logging.getLogger('statistics')


class ClientProvider(object):
    """Initialize clients for OpenStack component and expose them as attrs"""

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
                service_type=consts.NOVA_SERVICE_TYPE.compute,
                insecure=True
            )

        return self._nova

    @property
    def cinder(self):
        if self._cinder is None:
            self._cinder = cinder_client.Client(
                settings.OPENSTACK_API_VERSION["cinder"],
                *self.credentials,
                insecure=True
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
        """Create client based on returned from keystone server version data.

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
                return keystone_client_v2.Client(insecure=True, **auth_creds)
            elif version == 3:
                return keystone_client_v3.Client(insecure=True, **auth_creds)

        raise Exception("Failed to discover keystone version "
                        "for auth_url {0}".format(
                            auth_creds.get("auth_url"))
                        )

    @property
    def credentials(self):
        if self._credentials is None:
            cluster_attrs_editable = \
                objects.Cluster.get_editable_attributes(self.cluster)

            access_data = cluster_attrs_editable.get("workloads_collector")

            if not access_data:
                # in case there is no section for workloads_collector
                # in cluster attributes we try to fallback here to
                # default credential for the cluster. It is not 100%
                # foolproof as user might have changed them at this time
                access_data = cluster_attrs_editable["access"]

            os_user = access_data["user"]["value"]
            os_password = access_data["password"]["value"]
            os_tenant = access_data["tenant"]["value"]

            auth_host = utils.get_mgmt_ip_of_cluster_controller(self.cluster)
            auth_url = "http://{0}:{1}/{2}/".format(
                auth_host, settings.AUTH_PORT,
                settings.OPENSTACK_API_VERSION["keystone"])

            self._credentials = (os_user, os_password, os_tenant, auth_url)

        return self._credentials


def get_info_from_os_resource_manager(client_provider, resource_name):
    """Use OpenStack resource manager to retrieve information about resource

    Utilize clients provided by client_provider instance to retrieve
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

    client_api_version = utils.get_nested_attr(
        client_inst,
        client_provider.clients_version_attr_path[client_name]
    )

    matched_api = \
        resource_description["supported_api_versions"][client_api_version]

    resource_manager_name = matched_api["resource_manager_name"]
    resource_manager = getattr(client_inst, resource_manager_name)

    attributes_white_list = matched_api["attributes_white_list"]

    additional_display_options = \
        matched_api.get("additional_display_options", {})

    resource_info = _get_data_from_resource_manager(
        resource_manager,
        attributes_white_list,
        additional_display_options
    )

    return resource_info


def _get_data_from_resource_manager(resource_manager, attrs_white_list_rules,
                                    additional_display_options):
    data = []

    display_options = {}
    display_options.update(additional_display_options)

    instances_list = resource_manager.list(**display_options)
    for inst in instances_list:
        inst_details = {}

        obj_dict = \
            inst.to_dict() if hasattr(inst, "to_dict") else inst.__dict__

        for rule in attrs_white_list_rules:
            try:
                inst_details[rule.map_to_name] = utils.get_attr_value(
                    rule.path, rule.transform_func, obj_dict
                )
            except KeyError:
                # in case retrieved attribute is highlevel key
                # and is not present in obj_dict KeyError occurs which
                # cannot be handled by get_attr_value function due to
                # its features so we must do it here in order
                # to prevent from situation when whole set data is not
                # collected for particular resource
                logger.info("{0} cannot be collected for the statistic "
                            "as attribute with path {1} is not present in the "
                            "resource manager's data".format(rule.map_to_name,
                                                             rule.path))
        data.append(inst_details)

    return data


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
