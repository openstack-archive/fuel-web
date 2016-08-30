#    Copyright 2016 Mirantis, Inc.
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

from nailgun import errors

from adapter_base import PluginAdapterBase
from adapter_v1 import PluginAdapterV1
from adapter_v2 import PluginAdapterV2
from adapter_v3 import PluginAdapterV3
from adapter_v4 import PluginAdapterV4
from adapter_v5 import PluginAdapterV5

__plugins_mapping = {
    '1.0.': PluginAdapterV1,
    '2.0.': PluginAdapterV2,
    '3.0.': PluginAdapterV3,
    '4.0.': PluginAdapterV4,
    '5.0.': PluginAdapterV5
}


def get_supported_versions():
    return list(__plugins_mapping)


def get_adapter_for_package_version(plugin_version):
    """Get plugin adapter class for plugin version.

    :param plugin_version: plugin version string
    :type plugin_version: basestring|str

    :return: plugin loader class
    :rtype: loaders.PluginLoader|None
    """
    for plugin_version_head in __plugins_mapping:
        if plugin_version.startswith(plugin_version_head):
            return __plugins_mapping[plugin_version_head]


def wrap_plugin(plugin):
    """Creates plugin object with specific class version

    :param plugin: plugin db object
    :returns: cluster attribute object
    """
    package_version = plugin.package_version

    attr_class = get_adapter_for_package_version(package_version)

    if not attr_class:
        supported_versions = ', '.join(get_supported_versions())

        raise errors.PackageVersionIsNotCompatible(
            'Plugin id={0} package_version={1} '
            'is not supported by Nailgun, currently '
            'supported versions {2}'.format(
                plugin.id, package_version, supported_versions))

    return attr_class(plugin)
