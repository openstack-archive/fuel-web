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

import logging
import os

from fuel_upgrade.engines.host_system import HostSystemUpgrader
from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase

from fuel_upgrade import utils

logger = logging.getLogger(__name__)


class FixHostSystemRepoHook(PreUpgradeHookBase):
    """During 5.0.1 upgrade we add repository
    where as repository path we set path to
    repository which is from upgrade tar ball.
    When user deletes this information he deletes
    the repo. As result we can get broken repo
    which fails during the next upgrade [1].

    [1] https://bugs.launchpad.net/fuel/+bug/1358686
    """

    #: this hook is required only for host-system engine
    enable_for_engines = [HostSystemUpgrader]

    #: path to 5.0.1 repository which is created by upgrade script
    repo_path = '/var/www/nailgun/5.0.1/centos/x86_64'

    #: path to the file for yum repo
    yum_repo_file = '/etc/yum.repos.d/5.0.1_nailgun.repo'

    #: path to repo template
    repo_template = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', 'templates', 'nailgun.repo'))

    def __init__(self, *args, **kwargs):
        super(FixHostSystemRepoHook, self).__init__(*args, **kwargs)

    def check_if_required(self):
        """The hack is required if we're going to upgrade from 5.0.1
        and only repo path for 5.0.1 is exists
        """
        return (self.config.from_version == '5.0.1' and
                utils.file_exists(self.repo_path) and
                utils.file_exists(self.yum_repo_file))

    def run(self):
        """Change repo path
        """
        utils.render_template_to_file(
            self.repo_template,
            self.yum_repo_file,
            {'repo_path': self.repo_path, 'version': '5.0.1'})
