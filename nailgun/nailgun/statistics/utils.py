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

from collections import namedtuple
import os
import random
import six

from contextlib import contextmanager

from nailgun import consts
from nailgun.logger import logger
from nailgun.network import manager
from nailgun.settings import settings
from nailgun.statistics import errors


WhiteListRule = namedtuple(
    'WhiteListItem', ['path', 'map_to_name', 'transform_func'])


def get_mgmt_ip_of_cluster_controller(cluster):
    return manager.NetworkManager.get_ip_by_network_name(
        get_online_controller(cluster),
        consts.NETWORKS.management
    ).ip_addr


def get_proxy_for_cluster(cluster):
    proxy_host = get_online_controller(cluster).ip
    proxy_port = settings.OPENSTACK_INFO_COLLECTOR_PROXY_PORT
    proxy = "http://{0}:{1}".format(proxy_host, proxy_port)

    return proxy


def get_online_controller(cluster):
    online_controllers = filter(
        lambda node: ("controller" in node.roles and node.online is True),
        cluster.nodes
    )

    if not online_controllers:
        raise errors.NoOnlineControllers(
            "No online controllers could be found for cluster with id {0}"
            .format(cluster.id)
        )

    controller = online_controllers[0]

    return controller


def get_attr_value(path, func, attrs):
    """Gets attribute value from 'attrs' by specified
    'path'. In case of nested list - list of
    of found values will be returned
    :param path: list of keys for accessing the attribute value
    :param func: if not None - will be applied to the value
    :param attrs: attributes data
    :return: found value(s)
    """
    for idx, p in enumerate(path):
        if isinstance(attrs, (tuple, list)):
            result_list = []
            for cur_attr in attrs:
                try:
                    value = get_attr_value(path[idx:], func, cur_attr)
                    result_list.append(value)
                except (KeyError, TypeError):
                    pass
            return result_list
        else:
            attrs = attrs[p]
    if func is not None:
        attrs = func(attrs)
    return attrs


def get_nested_attr(obj, attr_path):
    # prevent from error in case of empty list and
    # None object
    if not all([obj, attr_path]):
        return None

    attr_name = attr_path[0]
    attr_value = getattr(obj, attr_name, None)

    # stop recursion as we already are on last level of attributes nesting
    if len(attr_path) == 1:
        return attr_value

    return get_nested_attr(attr_value, attr_path[1:])


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
