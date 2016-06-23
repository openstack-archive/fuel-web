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

from distutils.version import StrictVersion
import os
import shutil
import tarfile
import yaml

from nailgun import errors
from nailgun.plugins.package_manager import base
from nailgun.settings import settings


class PackageV1Handler(base.BasePackageHandler):

    @classmethod
    def install(cls, path):
        plugin_tar = tarfile.open(path, 'r')
        try:
            plugin_tar.extractall(settings.PLUGINS_PATH)
        finally:
            plugin_tar.close()

    @classmethod
    def reinstall(cls, path):
        metadata = cls.get_metadata(path)
        cls.remove(metadata['name'], metadata['version'])
        cls.install(path)

    @classmethod
    def upgrade(cls, _):
        raise errors.UpgradeIsNotSupported(
            "Upgrade action is not supported for plugins with package "
            "version '1.0.0'. You must use newer plugin format.")

    @classmethod
    def downgrade(cls, _):
        raise errors.DowngradeIsNotSupported(
            "Downgrade action is not supported for plugins with package "
            "version '1.0.0'. You must use newer plugin format.")

    @classmethod
    def remove(cls, name, version):
        plugin_path = os.path.join(settings.PLUGINS_PATH,
                                   '{0}-{1}'.format(name, version))
        shutil.rmtree(plugin_path)

    @classmethod
    def is_compatible(cls, package_version):
        v1 = StrictVersion('1.0.0')
        v2 = StrictVersion('2.0.0')
        return v1 <= StrictVersion(package_version) < v2

    @classmethod
    def get_metadata(cls, path):
        metadata = {}
        plugin_tar = tarfile.open(path, 'r')
        try:
            for member_name in plugin_tar.getnames():
                if base.CONFIG_METADATA in member_name:
                    metadata = yaml.load(
                        plugin_tar.extractfile(member_name).read()) or {}
                    break
            return metadata
        finally:
            plugin_tar.close()
