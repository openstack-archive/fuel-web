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
import cgi
from distutils.version import StrictVersion
import json
import os

import shutil
import six
import tempfile
import web

from nailgun import consts
from nailgun import errors
from nailgun.objects import PluginCollection
from nailgun.plugins.package_manager.package_fp import PluginPackageFP
from nailgun.plugins.package_manager.package_rpm import PluginPackageRPM
from nailgun import utils


@six.add_metaclass(abc.ABCMeta)
class BasePackageManager(object):

    @classmethod
    def _get_plugins_by(cls, **kwargs):
        """Retrieves base attributes of all versions of installed plugins.

        :param kwargs: Database query filter
        :type kwargs: dict
        :return: List of dictionaries with plugins attributes
        :rtype: list
        """
        return PluginCollection.to_list(
            PluginCollection.filter_by(None, **kwargs),
            fields=['id', 'name', 'version', 'package_version'])


class PackageInstallManager(BasePackageManager):

    def __init__(self):
        self.path, self.force = self._get_params_of_uploaded_file()
        self.handler = self._get_package_handler(self.path)
        self.metadata = self.handler.get_metadata(self.path)

        # retrieve plugin which can be updated
        self.plugin = {}
        major = self.handler.get_major_version(self.metadata['version'])
        options = dict(name=self.metadata['name'])
        for p in self._get_plugins_by(**options):
            if self.handler.get_major_version(p['version']) == major:
                self.plugin = p
                break

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        temp_dir = os.path.dirname(str(self.path))
        utils.remove_silently(temp_dir)

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
        :raise: errors.AlreadyExists
        """
        if not self.plugin:
            self.handler.install(self.path)
            return consts.PLUGIN_UPLOAD_RESULT.installed

        sv_p = StrictVersion(self.plugin['version'])
        sv_m = StrictVersion(self.metadata['version'])

        if sv_p == sv_m:
            if not self.force:
                raise errors.AlreadyExists(
                    "Plugin with the same version already exists")
            self.handler.reinstall(self.path)
            return consts.PLUGIN_UPLOAD_RESULT.reinstalled
        elif sv_p < sv_m:
            self.handler.upgrade(self.path)
            return consts.PLUGIN_UPLOAD_RESULT.upgraded
        else:
            self.handler.downgrade(self.path)
            return consts.PLUGIN_UPLOAD_RESULT.downgraded

    @staticmethod
    def _get_params_of_uploaded_file():
        """Saves uploaded file and gets parameters for its processing.

        :return: Path to uploaded file and value of 'force' flag
        :rtype: tuple
        :raises: errors.InvalidData
        """
        storage = web.input(uploaded={})
        uploaded_obj = storage['uploaded']

        if not isinstance(uploaded_obj, cgi.FieldStorage):
            raise errors.InvalidData('No uploaded file')

        temp_dir = tempfile.mkdtemp()
        path = os.path.join(temp_dir, uploaded_obj.filename)
        with open(path, 'w') as plugin_file:
            shutil.copyfileobj(uploaded_obj.file, plugin_file)

        return path, utils.parse_bool(storage.get('force'))

    @staticmethod
    def _get_package_handler(path):
        """Finds suitable class of plugin package handler by file extension.

        :param path: Path to plugin file
        :type path: str
        :return: Plugin package handler
        :rtype: class
        :raises: errors.PackageFormatIsNotCompatible |
                 errors.PackageVersionIsNotCompatible
        """
        packages = {'fp': PluginPackageFP, 'rpm': PluginPackageRPM}
        ext = os.path.splitext(path)[1][1:].lower()
        if ext not in packages:
            raise errors.PackageFormatIsNotCompatible(
                "Plugin '{0}' has unsupported format '{1}'".format(
                    os.path.basename(path), ext))

        handler = packages[ext]
        metadata = handler.get_metadata(path)
        if not handler.is_compatible(metadata.get('package_version', '0.0.0')):
            raise errors.PackageVersionIsNotCompatible()

        return handler


class PackageRemoveManager(BasePackageManager):

    def __init__(self, name, version, package_version=None):
        """Prepares environment for manipulation with package.

        :param name: Plugin name
        :type name: str
        :param version: Plugin version
        :type version: str
        :param package_version: Package version
        :type package_version: str
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

        :param package_version: Package version
        :type package_version: str
        :return: Plugin package handler
        :rtype: class
        :raise: errors.PackageVersionIsNotCompatible
        """
        for handler in PluginPackageFP, PluginPackageRPM:
            if handler.is_compatible(package_version):
                return handler
        raise errors.PackageVersionIsNotCompatible()
