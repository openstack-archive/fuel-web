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

import yaml


class Config(object):

    def __init__(self, config_file=None):
        self.config_file = config_file
        self.curdir = os.getcwd()
        self._config = {}

    @property
    def default_config(self):
        return {
            'library_dir': os.path.join(self.curdir, 'library'),
            'puppet_modules': '/etc/puppet/modules',
            'puppet_options': '',
            'report_dir': '/var/tmp/task_report',
            'pid_dir': '/var/tmp/task_run',
            'puppet_manifest': 'site.pp',
            'status_file': 'status',
            'debug': False,
            'task_file': 'task.yaml',
            'config_file': self.config_file}

    @property
    def config(self):
        if self._config:
            return self._config
        default_config = self.default_config
        if self.config_file and os.path.exists(default_config['config_file']):
            with open(default_config['config_file']) as f:
                self._config = yaml.load(f.read())
            return self._config
        return default_config

    def __getitem__(self, method_name):
        return self.config.get(method_name, None)

    def __repr__(self):
        return yaml.dump(self.config, default_flow_style=False)
