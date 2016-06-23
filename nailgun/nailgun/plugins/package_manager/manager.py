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
from nailgun.plugins.package_manager.package_v1 import PackageV1Handler
from nailgun.plugins.package_manager.package_v2 import PackageV2Handler


@six.add_metaclass(abc.ABCMeta)
class BasePackageManager(object):

    @classmethod
    def _get_plugins_by(cls, **kwargs):
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
        """Prepares environment for manipulation with package.

        :param str path: Path to plugin file
        :param bool force: Flag for reinstall or downgrade plugin
        :raise: errors.PackageVersionIsNotCompatible
        """
        self.path = path
        self.force = force
        self.handler = self._get_package_handler(path)
        self.metadata = self.handler.get_metadata(path)
        if not self.handler.is_compatible(
                self.metadata.get('package_version', '0.0.0')):
            raise errors.PackageVersionIsNotCompatible()

        # Retrieve plugin which can be updated
        self.plugin = {}
        major = self.handler.get_major_version(self.metadata['version'])
        options = dict(name=self.metadata['name'])
        for p in self._get_plugins_by(**options):
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

    def process_file(self):
        """Processing of uploaded plugin file.

        :return: Result of processing
        :rtype: str
        :raises: errors.AlreadyExists | errors.DowngradeIsDetected
        """
        if not self.plugin:
            self.handler.install(self.path)
            return 'installed'

        sv_p = StrictVersion(self.plugin['version'])
        sv_m = StrictVersion(self.metadata['version'])

        if sv_p == sv_m:
            if not self.force:
                raise errors.AlreadyExists(
                    "Plugin with the same version already exists")
            self.handler.reinstall(self.path)
            return 'reinstalled'
        elif sv_p < sv_m:
            self.handler.upgrade(self.path)
            return 'upgraded'
        elif self.force:
            self.handler.downgrade(self.path)
            return 'downgraded'
        else:
            raise errors.DowngradeIsDetected()

    @staticmethod
    def _get_package_handler(path):
        """Finds suitable class of plugin package handler by file extension.

        :param str path: Path to plugin file
        :return: Plugin handler
        :rtype: PackageV1Handler | PluginPackageV2
        :raise: errors.PackageFormatIsNotCompatible
        """
        pv = {'fp': PackageV1Handler, 'rpm': PackageV2Handler}
        ext = os.path.splitext(path)[1][1:].lower()
        if ext not in pv:
            raise errors.PackageFormatIsNotCompatible(
                "Plugin '{0}' has unsupported format '{1}'".format(
                    os.path.basename(path), ext))

        return pv[ext]


class PackageRemoveManager(BasePackageManager):

    def __init__(self, name, version, package_version=None):
        """Prepares environment for manipulation with package.

        :param str name: Plugin name
        :param str version: Plugin version
        :param str package_version: Package version
        :raise: errors.ObjectNotFound
        """
        self.name = name
        self.version = version
        options = dict(name=name, version=version)
        plugins = self._get_plugins_by(**options)
        self.plugin = plugins[0] if len(plugins) else None
        if not package_version and not self.plugin:
            raise errors.ObjectNotFound(
                "Cannot define suitable handler for plugin package.")
        pv = package_version or self.plugin['package_version']
        self.handler = self._get_package_handler(pv)

    def remove(self):
        """Removes plugin package from system."""
        self.handler.remove(self.name, self.version)

    @staticmethod
    def _get_package_handler(package_version):
        """Finds suitable class of plugin package handler by package version.

        :param str package_version: Package version
        :return: Plugin handler
        :rtype: PackageV1Handler | PluginPackageV2
        :raise: errors.PackageVersionIsNotCompatible
        """
        for handler in PackageV1Handler, PackageV2Handler:
            if handler.is_compatible(package_version):
                return handler
        raise errors.PackageVersionIsNotCompatible()
