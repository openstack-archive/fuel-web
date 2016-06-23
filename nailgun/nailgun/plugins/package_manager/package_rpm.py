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

import os
import yaml

from nailgun import consts
from nailgun.plugins.package_manager.base import BasePluginPackage
from nailgun.settings import settings
from nailgun import utils


class PluginPackageRPM(BasePluginPackage):

    @classmethod
    def install(cls, path):
        cmd = "rpm --dbpath {0} -i --nodeps {1}"
        utils.exec_cmd(cmd.format(settings.PLUGINS_RPM_DB_PATH, path))

    @classmethod
    def reinstall(cls, path):
        cmd = "rpm --dbpath {0} -i --nodeps --replacepkgs --replacefiles {1}"
        utils.exec_cmd(cmd.format(settings.PLUGINS_RPM_DB_PATH, path))

    @classmethod
    def upgrade(cls, path):
        cmd = "rpm --dbpath {0} -U --nodeps {1}"
        utils.exec_cmd(cmd.format(settings.PLUGINS_RPM_DB_PATH, path))

    @classmethod
    def downgrade(cls, path):
        cmd = "rpm --dbpath {0} -U --nodeps --oldpackage {1}"
        utils.exec_cmd(cmd.format(settings.PLUGINS_RPM_DB_PATH, path))

    @classmethod
    def remove(cls, name, version):
        cmd = "rpm --dbpath {0} -e --allmatches {1}-{2}"
        major_version = cls.get_major_version(version)
        utils.exec_cmd(cmd.format(
            settings.PLUGINS_RPM_DB_PATH, name, major_version))

    @classmethod
    def is_compatible(cls, package_version):
        return cls.check_package_version(package_version, '2.0.0')

    @classmethod
    def get_metadata(cls, path):
        cmd = "rpm2cpio {0} | cpio -i --quiet --to-stdout .{1}"
        mask = os.path.join(
            settings.PLUGINS_PATH, '*', consts.PLUGIN_CONFIG_METADATA)
        metadata = utils.exec_cmd(cmd.format(path, mask))
        return yaml.load(metadata) or {}
