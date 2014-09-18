# Copyright 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import jinja2
import json
import os
import sys
import time

try:
    from unittest.case import TestCase
except ImportError:
    # Runing unit-tests in production environment
    from unittest2.case import TestCase
import yaml

from fuel_agent_ci.objects import environment
from fuel_agent_ci import utils

# FIXME(kozhukalov) it is better to set this as command line arg
ENV_FILE = os.path.join(os.path.dirname(__file__),
                        '../../samples/ci_environment.yaml')


class BaseFuelAgentCITest(TestCase):
    FUEL_AGENT_REPO_NAME = 'fuel_agent'
    FUEL_AGENT_HTTP_NAME = 'http'
    FUEL_AGENT_NET_NAME = 'net'
    FUEL_AGENT_DHCP_NAME = 'dhcp'
    FUEL_AGENT_SSH_NAME = 'vm'
    FUEL_AGENT_TEMPLATE_PATH = '/usr/share/fuel-agent/cloud-init-templates'

    def setUp(self):
        super(BaseFuelAgentCITest, self).setUp()

        # Starting environment
        with open(ENV_FILE) as f:
            ENV_DATA = (yaml.load(f.read()))
        self.env = environment.Environment.new(**ENV_DATA)
        self.env.start()

        self.repo = self.env.repo_by_name(self.FUEL_AGENT_REPO_NAME)
        self.ssh = self.env.ssh_by_name(self.FUEL_AGENT_SSH_NAME)
        self.http = self.env.http_by_name(self.FUEL_AGENT_HTTP_NAME)
        self.dhcp_hosts = self.env.dhcp_by_name(self.FUEL_AGENT_DHCP_NAME).hosts
        self.net = self.env.net_by_name(self.FUEL_AGENT_NET_NAME)

        self.ssh.wait()
        self._upgrade_fuel_agent()

    def _upgrade_fuel_agent(self):
        """This method is to be deprecated when artifact
        based build system is ready.
        """
        src_dir = os.path.join(self.env.envdir, self.repo.path, 'fuel_agent')
        package_name = 'fuel-agent-0.1.0.tar.gz'

        # Building fuel-agent pip package
        utils.execute('python setup.py sdist', cwd=src_dir)

        # Putting fuel-agent pip package on a node
        self.ssh.put_file(
            os.path.join(src_dir, 'dist', package_name),
            os.path.join('/tmp', package_name))

        # Installing fuel_agent pip package
        self.ssh.run('pip install --upgrade %s' %
                     os.path.join('/tmp', package_name))

        # Copying fuel_agent templates
        self.ssh.run('mkdir -p %s' % self.FUEL_AGENT_TEMPLATE_PATH)
        for f in os.listdir(
                os.path.join(src_dir, 'cloud-init-templates')):
            if f.endswith('.jinja2'):
                self.ssh.put_file(
                    os.path.join(src_dir, 'cloud-init-templates', f),
                    os.path.join(self.FUEL_AGENT_TEMPLATE_PATH, f))

        self.ssh.put_file(
            os.path.join(src_dir, 'etc/fuel-agent/fuel-agent.conf.sample'),
            '/etc/fuel-agent/fuel-agent.conf')

    def tearDown(self):
        super(BaseFuelAgentCITest, self).tearDown()
        self.env.stop()

    def render_template(self,
                        template_name,
                        template_dir=os.path.join(os.path.dirname(__file__),
                                                  'templates'),
                        template_data=None):
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
        template = env.get_template(template_name)
        return template.render(**(template_data or {}))
