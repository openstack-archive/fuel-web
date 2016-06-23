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

import six

CONFIG_METADATA = 'metadata.yaml'


@six.add_metaclass(abc.ABCMeta)
class BasePackageHandler(object):

    @classmethod
    @abc.abstractmethod
    def install(cls, path):
        """Installs a plugin package on file system.

        :param str path: Path to plugin's package file
        """

    @classmethod
    @abc.abstractmethod
    def reinstall(cls, path):
        """Reinstall a plugin with the same version.

        :param str path: Path to plugin's package file
        """

    @classmethod
    @abc.abstractmethod
    def upgrade(cls, path):
        """Upgrades a plugin.

        :param str path: Path to plugin's package file
        """

    @classmethod
    @abc.abstractmethod
    def downgrade(cls, path):
        """Downgrades a plugin.

        :param str path: Path to plugin's package file
        """

    @classmethod
    @abc.abstractmethod
    def remove(cls, name, version):
        """Removes a plugin from file system.

        :param str name: Plugin name
        :param str version: Full plugin version
        """

    @classmethod
    @abc.abstractmethod
    def is_compatible(cls, package_version):
        """Check compatibility using version of plugin package.

        :param str package_version: Package version
        :return: Result of checking
        :rtype: bool
        """

    @classmethod
    @abc.abstractmethod
    def get_metadata(cls, path):
        """Retrieves plugin metadata from package.

        :param str path: Path to plugin's package file
        :return: Plugin metadata
        :rtype: dict
        """

    @staticmethod
    def get_major_version(version):
        """Retrieves major version of plugin (1.2.3 -> 1.2).

        :param str version: Full plugin version
        :return: Only major plugin version
        :rtype: str
        """
        version_tuple = StrictVersion(version).version
        return '.'.join(map(str, version_tuple[:2]))
