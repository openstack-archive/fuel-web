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

from copy import deepcopy

import yaml

from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase
from fuel_upgrade.engines.docker_engine import DockerUpgrader

from fuel_upgrade import utils


class AddCredentialsHook(PreUpgradeHookBase):
    """Feature `access control on master node`
    was introduced in 5.1 release [1].

    In this feature fuelmenu generates credenitals
    and saves them in /etc/astute.yaml file.

    Before upgrade for this featuer we need to
    add default credentials to the file. 

    [1] https://blueprints.launchpad.net/fuel/+spec/access-control-master-node
    """

    #: This hook required only for docker engine
    _enable_for_engines = []

    #: Default credentials
    credentials = {
        "astute/user": "naily",
        "astute/password": "naily",
        "cobbler/user": "cobbler",
        "cobbler/password": "cobbler",
        "mcollective/user": "mcollective",
        "mcollective/password": "marionette",
        "postgres/keystone_dbname": "keystone",
        "postgres/keystone_user": "keystone",
        "postgres/keystone_password": "keystone",
        "postgres/nailgun_dbname": "nailgun",
        "postgres/nailgun_user": "nailgun",
        "postgres/nailgun_password": "nailgun",
        "postgres/ostf_dbname": "ostf",
        "postgres/ostf_user": "ostf",
        "postgres/ostf_password": "ostf"}

    @property
    def is_required(self):
        """Checks if it's required to run upgrade

        :returns: True - if it is required to run this hook
                  False - if it is not required to run this hook
        """
        is_required = not all(key in self.config.astute
                              for key in self.credentials.keys())

        return is_required

    def run(self):
        """Adds default credentials to config file
        """
        astute_config = deepcopy(self.config.astute)
        astute_config.update(self.credentials)

        # NOTE(eli): Just save file for backup in case
        # if user want to restore it manually
        utils.copy_file(
            self.config.current_fuel_astute_path,
            '{0}_{1}'.format(self.config.current_fuel_astute_path,
                             self.config.from_version),
            overwrite=False)

        with open(self.config.current_fuel_astute_path, 'w') as f:
            astute_str = yaml.dump(astute_config, default_flow_style=False)
            f.write(astute_str)
