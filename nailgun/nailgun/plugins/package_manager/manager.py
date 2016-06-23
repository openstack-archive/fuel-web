# -*- coding: utf-8 -*-

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

import abc
from distutils.version import StrictVersion
import json
import os

import six

from nailgun import errors
from nailgun.objects import PluginCollection
from nailgun.plugins.package_manager.package_v1 import PluginPackageV1
from nailgun.plugins.package_manager.package_v2 import PluginPackageV2


@six.add_metaclass(abc.ABCMeta)
class BasePackageManager(object):

    @classmethod
    def _get_attrs(cls, **kwargs):
        """Retrieves base attributes of all versions of installed plugins.

        :param dict kwargs: Database query filter
        :return: List of dictionaries with plugins attributes
        :rtype: list
        """
        return PluginCollection.to_list(
            PluginCollection.filter_by(None, **kwargs),
            fields=['id', 'name', 'version', 'package_version'])


class PackageInstallManager(BasePackageManager):

    def __init__(self, path, force):
        """Prepare environment for manipulation with package.

        :param str path: Path to plugin file
        :param bool force: Flag for reinstall or downgrade plugin
        :raise: errors.PackageVersionIsNotCompatible
        """
        self.action = None
        self.path = path
        self.force = force
        self.handler = self._get_obj_by_file(path)
        self.metadata = self.handler.get_metadata(path)
        if not self.handler.is_compatible(
                self.metadata.get('package_version', '0.0.0')):
            raise errors.PackageVersionIsNotCompatible()

        # Retrieve plugin which can be updated
        self.plugin = {}
        major = self.handler.get_major_version(self.metadata['version'])
        options = dict(name=self.metadata['name'])
        for p in self._get_attrs(**options):
            if self.handler.get_major_version(p['version']) == major:
                self.plugin = p
                break

    def get_metadata(self):
        """Get metadata from package.

        :return: Plugin metadata as json formatted string
        :rtype: str
        """
        return json.dumps(self.metadata)

    def get_plugin_id(self):
        """Get ID of installed plugin.

        :return: Plugin ID
        :rtype: int | None
        """
        return self.plugin.get('id')

    def get_last_action(self):
        """Get the last action with the plugin.

        :return: Last action
        :rtype: str | None
        """
        return self.action

    def process_file(self):
        """Processing of uploaded plugin file.

        :raises: errors.AlreadyExists | errors.DowngradeIsDetected
        """
        if not self.plugin:
            self.handler.install(self.path)
            self.action = 'installed'
            return

        sv_p = StrictVersion(self.plugin['version'])
        sv_m = StrictVersion(self.metadata['version'])

        if sv_p == sv_m:
            if not self.force:
                raise errors.AlreadyExists(
                    "Plugin with the same version already exists")
            self.handler.reinstall(self.path)
            self.action = 'reinstalled'
        elif sv_p < sv_m:
            self.handler.upgrade(self.path)
            self.action = 'upgraded'
        elif self.force:
            self.handler.downgrade(self.path)
            self.action = 'downgraded'
        else:
            raise errors.DowngradeIsDetected()

    @staticmethod
    def _get_obj_by_file(path):
        """Finds appropriate class of plugin handler by file extension.

        :param str path: Path to plugin file
        :return: Plugin handler
        :rtype: PluginPackageV1 | PluginPackageV2
        :raise: errors.PackageFormatIsNotCompatible
        """
        pv = {'fp': PluginPackageV1, 'rpm': PluginPackageV2}
        ext = os.path.splitext(path)[1][1:].lower()
        if ext not in pv:
            raise errors.PackageFormatIsNotCompatible(
                "Plugin '{0}' has unsupported format '{1}'".format(
                    os.path.basename(path), ext))

        return pv[ext]


class PackageRemoveManager(BasePackageManager):

    def __init__(self, name, version):
        """Prepare environment for manipulation with package.

        :param str name: Plugin name
        :param str version: Plugin version
        :raise: errors.ObjectNotFound
        """
        self.name = name
        self.version = version
        options = dict(name=name, version=version)
        attrs = self._get_attrs(**options)
        self.plugin = attrs[0] if len(attrs) else None
        self.handler = None

    def set_handler(self, package_version=None):
        """Set handler for plugin package.

        :param str package_version: Package version
        """
        if not package_version and not self.plugin:
            raise errors.ObjectNotFound()
        pv = package_version or self.plugin['package_version']
        self.handler = self._get_obj_by_attr(pv)

    def remove(self):
        """Remove plugin package from system."""
        if self.handler is not None:
            self.handler.remove(self.name, self.version)

    @staticmethod
    def _get_obj_by_attr(package_version):
        """Finds appropriate class of plugin handler by package version.

        :param str package_version: Package version
        :return: Plugin handler
        :rtype: PluginPackageV1 | PluginPackageV2
        :raise: errors.PackageVersionIsNotCompatible
        """
        for handler in PluginPackageV1, PluginPackageV2:
            if handler.is_compatible(package_version):
                return handler
        raise errors.PackageVersionIsNotCompatible()
