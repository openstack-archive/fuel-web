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

import functools
import traceback

from stevedore import NamedExtensionManager

from nailgun.logger import logger


objs_cache = {}


def load_failure_callback(manager, plugin, exception):
    logger.error(
        u"Failed to load plugin '{0}': {1}".format(
            plugin.module_name,
            traceback.format_exc(exception)
        )
    )


def plugin_hook(name):
    def decorator(func):
        @functools.wraps(func)
        def decorated(*args, **kwargs):
            namespace = 'nailgun.custom_roles'

            manager = objs_cache.setdefault(
                name,
                NamedExtensionManager(
                    namespace,
                    [name],
                    invoke_on_load=True,
                    propagate_map_exceptions=True,
                    on_load_failure_callback=load_failure_callback
                )
            )

            plugin_result = []

            def handle_custom_roles(ext):
                return getattr(ext.obj, name)(*args, **kwargs)

            if manager.extensions:
                plugin_result += manager.map(handle_custom_roles)
            else:
                result = func(*args, **kwargs)
                plugin_result.append(result)

            # TODO(enchantner): reduce
            return plugin_result[-1]
            # return result
        return decorated
    return decorator
