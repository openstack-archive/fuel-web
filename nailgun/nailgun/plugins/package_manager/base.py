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


@six.add_metaclass(abc.ABCMeta)
class BasePluginPackage(object):

    @classmethod
    @abc.abstractmethod
    def install(cls, path):
        """Installs a plugin package on file system.

        :param path: Path to plugin's package file
        :type path: str
        """

    @classmethod
    @abc.abstractmethod
    def reinstall(cls, path):
        """Reinstall a plugin with the same version.

        :param path: Path to plugin's package file
        :type path: str
        """

    @classmethod
    @abc.abstractmethod
    def upgrade(cls, path):
        """Upgrades a plugin.

        :param path: Path to plugin's package file
        :type path: str
        """

    @classmethod
    @abc.abstractmethod
    def downgrade(cls, path):
        """Downgrades a plugin.

        :param path: Path to plugin's package file
        :type path: str
        """

    @classmethod
    @abc.abstractmethod
    def remove(cls, name, version):
        """Removes a plugin from file system.

        :param name: Plugin name
        :type name: str
        :param version: Full plugin version
        :type version: str
        """

    @classmethod
    @abc.abstractmethod
    def get_metadata(cls, path):
        """Retrieves plugin metadata from package.

        :param path: Path to plugin's package file
        :type path: str
        :return: Plugin metadata
        :rtype: dict
        """

    @classmethod
    @abc.abstractmethod
    def is_compatible(cls, package_version):
        """Verifies compatibility with the package version.

        :param str package_version: Package version
        :return: Result of checking
        :rtype: bool
        """

    @staticmethod
    def check_package_version(package_version, lowest, highest=None):
        """Check package version belong to version range.

        :param package_version: Plugin package version
        :type package_version: str
        :param lowest: Lowest package version
        :type lowest: str
        :param highest: Highest package version
        :type highest: str
        :return: Result of checking
        :rtype: bool
        """
        version = StrictVersion(package_version)
        low_version = StrictVersion(lowest)
        if highest is None:
            return low_version <= version
        high_version = StrictVersion(highest)
        return low_version <= version < high_version

    @staticmethod
    def get_major_version(version):
        """Retrieves major version of plugin (1.2.3 -> 1.2).

        :param version: Full plugin version
        :type version: str
        :return: Only major plugin version
        :rtype: str
        """
        version_tuple = StrictVersion(version).version
        return '.'.join(map(str, version_tuple[:2]))
