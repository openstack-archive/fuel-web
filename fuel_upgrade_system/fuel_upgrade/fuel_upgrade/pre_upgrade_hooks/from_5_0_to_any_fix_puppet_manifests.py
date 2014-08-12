# -*- coding: utf-8 -*-

#    Copyright 2014 Mirantis, Inc.
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

from fuel_upgrade.engines.openstack import OpenStackUpgrader
from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase

from fuel_upgrade.utils import copy
from fuel_upgrade.utils import iterfiles


class FixPuppetManifests(PreUpgradeHookBase):
    """Install new puppets for some releases in order to deliver fixes.

    Openstack Patching was introduced in Fuel 5.1, but we need to distribute
    some fixes for old puppet manifests of both 5.0 and 5.0.1 releases in
    order to provide working rollback feature.
    """

    #: this hook is required only for openstack engine
    enable_for_engines = [OpenStackUpgrader]

    #: a path to puppet scripts with fixes
    src_path = os.path.join('{update_path}', 'config', '{version}')
    #: a path to puppet destination
    dst_path = os.path.join('/etc', 'puppet')

    def __init__(self, *args, **kwargs):
        super(FixPuppetManifests, self).__init__(*args, **kwargs)

        # get source/destination directory pairs to install manifests
        if os.path.exists(os.path.join(self.dst_path, '5.0.1')):
            # we've detected that the master node was previously upgraded
            # from 5.0 to 5.0.1, so we have to install patched puppets
            # for both 5.0 and 5.0.1 releases
            self._copypairs = [
                (
                    self.src_path.format(
                        update_path=self.config.update_path, version='5.0'),
                    self.dst_path
                ),
                (
                    self.src_path.format(
                        update_path=self.config.update_path, version='5.0.1'),
                    os.path.join(self.dst_path, '5.0.1')
                )]
        else:
            # we've detected that the master node's previous installation
            # was fresh, so we have to install patched puppets only for
            # the current release
            self._copypairs = [
                (
                    self.src_path.format(
                        update_path=self.config.update_path,
                        version=self.config.from_version),
                    self.dst_path
                )]

    def check_if_required(self):
        """The hack is required if we're going to upgrade from 5.0 or 5.0.1.
        """
        return self.config.from_version in ('5.0', '5.0.1')

    def run(self):
        """Install patched manifests to the master node.
        """
        for srcpath, dstpath in self._copypairs:
            # we can't just copy folder as is, since it's not a full and
            # overwrite mode will erase entire old content
            for srcfile in iterfiles(srcpath):
                copy(srcfile, srcfile.replace(srcpath, dstpath))
