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

import glob
import os

from fuel_upgrade.clients import SupervisorClient
from fuel_upgrade.engines.base import UpgradeEngine
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

        #: packages to be installed before running puppet
        self.packages = self.host_system_config['install_packages']

        self.supervisor = SupervisorClient(
            self.config, self.config.from_version)

    @property
    def required_free_space(self):
        """Required free space to run upgrade

        Requires a lot of disk spaces for new repos and repo config.

        :returns: dict where key is path to directory
                  and value is required free space in megabytes
        """
        sources = glob.glob(self.host_system_config['repos']['src'])
        repos_size = sum(map(utils.dir_size, sources))

        return {
            self.host_system_config['repos']['dst']: repos_size,
            self.repo_config_path: 10,
        }

    def upgrade(self):
        """Run host system upgrade process
        """
        # The workaround we need in order to fix [1]. In few words,
        # when new Docker is installed the containers MUST NOT start
        # again because in this case puppet inside them will install
        # latest packages and breaks dependencies in some soft.
        #
        # [1]: https://bugs.launchpad.net/fuel/+bug/1455419
        self.supervisor.stop_all_services()

        self.install_repos()
        self.update_repo()
        self.install_packages()
        self.run_puppet()

    def rollback(self):
        """The only thing which we can rollback here
        is yum config
        """
        self.remove_repo_config()
        self.remove_repos()

        self.supervisor.start_all_services()

    def install_repos(self):
        sources = glob.glob(self.host_system_config['repos']['src'])
        for source in sources:
            destination = os.path.join(
                self.host_system_config['repos']['dst'],
                os.path.basename(source))
            utils.copy(source, destination)

    def remove_repos(self):
        sources = glob.glob(self.host_system_config['repos']['src'])
        for source in sources:
            destination = os.path.join(
                self.host_system_config['repos']['dst'],
                os.path.basename(source))
            utils.remove(destination)

    def update_repo(self):
        """Add new centos repository
        """
        utils.render_template_to_file(
            self.repo_template_path,
            self.repo_config_path,
            {'version': self.version,
             'repo_path': self.host_system_config['repo_master']})
        utils.exec_cmd('yum clean all')

    def install_packages(self):
        """Install packages for new release
        """
        for package in self.packages:
            utils.exec_cmd('yum install -v -y {0}'.format(package))

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
