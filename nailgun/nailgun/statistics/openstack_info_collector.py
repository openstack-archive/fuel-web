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

import os
import six

from contextlib import contextmanager

from novaclient import client as nova_client

from nailgun import consts
from nailgun.logger import logger
from nailgun.network import manager
from nailgun import objects
from nailgun.settings import settings


class _Missing(object):
    def __repr__(self):
        return "no value"


_missing = _Missing()


class cached_property(object):
    """Inspired by werkzeug progect's code:
    https://github.com/mitsuhiko/werkzeug/blob/master/werkzeug/utils.py#L35-L73

    Quotation from the class' documentation:
        'A decorator that converts a function into a lazy property.  The
    function wrapped is called the first time to retrieve the result
    and then that calculated result is used the next time you access
    the value::
        class Foo(object):
            @cached_property
            def foo(self):
                # calculate something important here
                return 42
    The class has to have a `__dict__` in order for this property to
    work.'
    """
    def __init__(self, func, name=None, doc=None):
        self.__name__ = name or func.__name__
        self.__module__ = func.__module__
        self.__doc__ = doc or func.__doc__
        self.func = func

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        value = obj.__dict__.get(self.__name__, _missing)
        if value is _missing:
            value = self.func(obj)
            obj.__dict__[self.__name__] = value
        return value


class OpenStackInfoCollector(object):
    """Introduce interface for collecting
    info from OpenStack installation

    Side effect: set 'http_proxy' environment variable
    for the time of request to OpenStack components
    """

    collected_attributes = {
        "nova_client": [
            {
                "manager_name": "servers",
                "resource_attributes": [
                    "id",
                    "name",
                    "status",
                    "user_id",
                    "tenant_id",
                    "OS-EXT-STS:power_state",
                    "OS-EXT-AZ:availability_zone",
                    "created",
                    "image",
                    "flavor",
                    "os-extended-volumes:volumes_attached",
                    "networks",
                    "diagnostics",
                ],
            },
        ],
    }

    def __init__(self, cluster):
        self.cluster = cluster
        self.nova = None

    @contextmanager
    def set_proxy(self, proxy):
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
            logger.exception("Error while interacting with "
                             "OpenStack api. Details: {0}"
                             .format(six.text_type(e)))
        finally:
            if proxy_old_value:
                logger.info("Restoring old value for http_proxy")
                os.environ["http_proxy"] = proxy_old_value
            else:
                logger.info("Deleting set http_proxy environment variable")
                del(os.environ["http_proxy"])

    @cached_property
    def proxy(self):
        proxy_host = self.online_controller.ip
        proxy_port = settings.OPENSTACK_INFO_COLLECTOR_PROXY_PORT
        proxy = "http://{0}:{1}".format(proxy_host, proxy_port)

        return proxy

    @cached_property
    def online_controller(self):
        online_controller = filter(
            lambda node: (
                "controller" in node.roles and node.online is True),
            self.cluster.nodes
        )[0]

        return online_controller

    # property is used here to make it convinient to automate
    # getting attributes described in 'collected_attributes' map
    # from the class using getattr function
    @property
    def nova_client(self):
        if self.nova is None:
            self.nova = nova_client.Client(
                settings.OPENSTACK_API_VERSION["nova"],
                *self.auth_creds,
                service_type=consts.NOVA_SERVICE_TYPE.compute
            )

        return self.nova

    @cached_property
    def auth_creds(self):
        access_data = objects.Cluster.get_creds(self.cluster)

        os_user = access_data["user"]["value"]
        os_password = access_data["password"]["value"]
        os_tenant = access_data["tenant"]["value"]

        auth_host = self.get_host_for_auth(self.cluster)
        auth_url = "http://{0}:{1}/v2.0/".format(auth_host,
                                                 settings.AUTH_PORT)

        auth_creds = (os_user, os_password, os_tenant, auth_url)

        return auth_creds

    def get_host_for_auth(self):
        return manager.NetworkManager._get_ip_by_network_name(
            self.online_controller, consts.NETWORKS.management
        ).ip_addr

    def get_info(self):
        openstack_info = {}

        with self.set_proxy(self.proxy):
            for client_name in self.collected_attributes:
                client_inst = getattr(self, client_name)

                client_data = {}

                for entity in self.collected_attributes[client_name]:
                    res_manager_name = entity["manager_name"]
                    res_manager_inst = getattr(client_inst,
                                               res_manager_name,
                                               None)
                    if res_manager_inst:
                        res_data = []

                        list_of_resources = res_manager_inst.list()

                        for res in list_of_resources:
                            attr_data = {}
                            for attr_name in entity["resource_attributes"]:
                                attr_value = getattr(res, attr_name, None)

                                # for attributes with composite names
                                if ":" in attr_name:
                                    attr_name = attr_name.split(":")[1]

                                attr_data[attr_name] = attr_value

                            res_data.append(attr_data)

                        client_data[res_manager_name] = {
                            "resources_data": res_data,
                            "resources_count": len(list_of_resources)
                        }

                openstack_info[client_name] = client_data

            openstack_info["images"] = self.get_images_info()

        return openstack_info

    def get_images_info(self):
        images = self.nova_client.images.list()

        size_attr_name = consts.OPENSTACK_IMAGES_SETTINGS.size_attr_name

        images_info = []
        for img in images:
            images_info.append(
                {
                    "size": getattr(img, size_attr_name, 0),
                    "unit": consts.OPENSTACK_IMAGES_SETTINGS.size_unit
                }
            )

        return images_info
