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

from fuel_upgrade.engines.base import UpgradeEngine
from fuel_upgrade.health_checker import FuelUpgradeVerify
from fuel_upgrade import utils


class HostSystemUpgrader(UpgradeEngine):
    """Upgrader for master node host system.
    Required for upgrading of packages which
    are not under docker, for example fuelclient,
    dockerctl.

    * add local repo with new packages
    * run puppet apply
    """

    templates_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '../templates'))

    def __init__(self, *args, **kwargs):
        super(HostSystemUpgrader, self).__init__(*args, **kwargs)

        #: host system upgarder specific configs
        self.host_system_config = self.config.host_system

        #: path to puppet manifests
        self.manifest_path = self.host_system_config['manifest_path']

        #: path to puppet modules
        self.puppet_modules_path = self.host_system_config[
            'puppet_modules_path']

        #: path to repo template
        self.repo_template_path = os.path.join(
            self.templates_dir, 'nailgun.repo')

        #: new version of fuel
        self.version = self.config.new_version

        #: path to repository config
        self.repo_config_path = self.host_system_config['repo_config_path']

        #: src repository path
        self.repo_src = self.host_system_config['repo_path']['src']

        #: dst repository path
        self.repo_dst = self.host_system_config['repo_path']['dst']

        #: we need it to make sure that all works fine after
        #: docker upgrading
        self.upgrade_verifier = FuelUpgradeVerify(self.config)

    @property
    def required_free_space(self):
        """Required free space to run upgrade

        Requires only several megabytes for
        repo config.

        :returns: dict where key is path to directory
                  and value is required free space
        """
        return {self.repo_config_path: 10}

    def upgrade(self):
        """Run host system upgrade process
        """
        self.copy_repo()
        self.update_repo()
        self.run_puppet()

        # Verify that all services up and running
        self.upgrade_verifier.verify()

    def rollback(self):
        """The only thing which we can rollback here
        is yum config
        """
        self.remove_repo_config()

    def on_success(self):
        """Do nothing for this engine
        """

    def copy_repo(self):
        """Copy centos repo on the host system.
        We need to make sure that when user
        removes temporary files after upgrade
        his repo path is valid.
        """
        utils.copy(self.repo_src, self.repo_dst)

    def update_repo(self):
        """Add new centos repository
        """
        utils.render_template_to_file(
            self.repo_template_path,
            self.repo_config_path,
            {'version': self.version,
             'repo_path': self.repo_dst})

    def run_puppet(self):
        """Run puppet to upgrade host system
        """
        utils.exec_cmd(
            'puppet apply -d -v '
            '{0} --modulepath={1}'.format(
                self.manifest_path, self.puppet_modules_path))

    def remove_repo_config(self):
        """Remove yum repository config
        """
        utils.remove_if_exists(self.repo_config_path)
