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

import functools
import traceback

import six

from stevedore import ExtensionManager
from stevedore import NamedExtensionManager

from nailgun.logger import logger


PLUGIN_NAMESPACE = 'nailgun.plugin'
API_NAMESPACE = 'nailgun.rest_api'
CUSTOM_ROLES_NAMESPACE = 'nailgun.custom_roles'

objs_cache = {}
plugins = {}
api_plugins = {}


def load_failure_callback(manager, plugin, exception):
    logger.error(
        u"Failed to load plugin '{0}': {1}".format(
            plugin.module_name,
            traceback.format_exc(exception)
        )
    )


def get_by_namespace(namespace):
    res = {}
    manager = ExtensionManager(
        namespace=namespace,
        invoke_on_load=False,
        on_load_failure_callback=load_failure_callback
    )
    for ext in manager.extensions:
        instance = ext.plugin()
        res[instance.plugin_name] = instance
    return res


def get_all_plugins():
    global plugins
    if not plugins:
        plugins = get_by_namespace(PLUGIN_NAMESPACE)
    return plugins


def get_api_plugins():
    global api_plugins
    if not api_plugins:
        for name, p in six.iteritems(get_by_namespace(API_NAMESPACE)):
            if not hasattr(p, "application"):
                logger.warning(
                    "Plugin '{0}' exposes 'nailgun.rest_api' namespace, but "
                    "doesn't provide proper WSGI application".format(name)
                )
            else:
                api_plugins[name] = p
    return api_plugins


def plugin_hook(name):
    def decorator(func):
        @functools.wraps(func)
        def decorated(*args, **kwargs):
            manager = objs_cache.setdefault(
                name,
                NamedExtensionManager(
                    CUSTOM_ROLES_NAMESPACE,
                    [name],
                    invoke_on_load=True,
                    propagate_map_exceptions=True,
                    on_load_failure_callback=load_failure_callback
                )
            )

            def handle_custom_roles(ext):
                return getattr(ext.obj, name)(*args, **kwargs)

            if manager.extensions:
                plugin_result_list = manager.map(handle_custom_roles)
                check_result = plugin_result_list[0]
                # TODO(enchantner): research & discuss
                if isinstance(check_result, list):
                    plugin_result = []
                    map(plugin_result.extend, plugin_result_list)
                elif isinstance(check_result, dict):
                    plugin_result = {}
                    map(plugin_result.update, plugin_result_list)
                else:
                    # only one result if we don't know how to merge it
                    return plugin_result_list[0]
            else:
                result = func(*args, **kwargs)
                plugin_result = result
            return plugin_result
        return decorated
    return decorator
