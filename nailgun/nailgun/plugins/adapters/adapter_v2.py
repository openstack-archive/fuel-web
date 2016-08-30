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

from distutils.version import StrictVersion

from nailgun.plugins.adapters import PluginAdapterBase
from nailgun.plugins import loaders


class PluginAdapterV2(PluginAdapterBase):
    """Plugins attributes class for package version 2.0.0."""
    # adapter v2 inheritance should be skipped

    loader_class = loaders.PluginLoaderV1

    @property
    def path_name(self):
        """Returns a name and major version of the plugin

        e.g. if there is a plugin with name "plugin_name" and version
        is "1.0.0", the method returns "plugin_name-1.0".

        It's different from previous version because in previous
        version we did not have plugin updates, in 2.0.0 version
        we should expect different plugin path.

        See blueprint: https://blueprints.launchpad.net/fuel/+spec
                              /plugins-security-fixes-delivery
        """
        return u'{0}-{1}'.format(self.plugin.name, self._major_version)

    @property
    def _major_version(self):
        """Returns major version of plugin's version

        e.g. if plugin has 1.2.3 version, the method returns 1.2
        """
        version_tuple = StrictVersion(self.plugin.version).version
        major = '.'.join(map(str, version_tuple[:2]))

        return major
