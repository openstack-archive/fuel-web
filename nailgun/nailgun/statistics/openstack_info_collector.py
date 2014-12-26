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


class ClientProvider(object):
    """Initialize clients for OpenStack components
    and expose them as attributes
    """

    def __init__(self, credentials):
        self.credentials = credentials

    @cached_property
    def nova(self):
        return nova_client.Client(
            settings.OPENSTACK_API_VERSION["nova"],
            *self.auth_creds,
            service_type=consts.NOVA_SERVICE_TYPE.compute
        )


class OpenStackInfoCollector(object):
    """Introduce interface for collecting
    info from OpenStack installation

    Side effect: set 'http_proxy' environment variable
    for the time of request to OpenStack components
    """

    collected_attributes = {
        "nova": {
            "servers": [
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
        }
    }

    equally_processed = ("nova",)

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

    @property
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

    @cached_property
    def client_provider(self):
        return ClientProvider(self.auth_creds)

    @property
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
            for component_name in self.equally_processed:
                openstack_info[component_name] = \
                    self._get_component_info(component_name)

            openstack_info["images"] = self.get_images_info()

        return openstack_info

    def _get_component_info(self, comp_name):
        comp_info = {}

        try:
            comp_client = getattr(self.client_provider, comp_name)

            comp_managers = self.collected_attributes[comp_name]

            for manager_name in comp_managers:
                manager_inst = getattr(comp_client, manager_name)

                manager_info = []
                for instance in manager_inst.list():
                    instance_info = {}
                    for attr_name in comp_managers[manager_name]:
                        instance_info[attr_name] = getattr(instance, attr_name)

                    manager_info.append(instance_info)

            comp_info[manager_name] = {
                'instances_info': manager_info,
                'instances_count': len(manager_inst.list())
            }
        except Exception as e:
            logger.exception("Collecting info from {0} failed. Details: {1}"
                             .format(comp_name, six.text_type(e)))

        return comp_info

    def get_images_info(self):
        images = self.client_provider.nova.images.list()

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
