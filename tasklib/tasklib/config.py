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
            'library_dir': '/etc/puppet/tasks',
            'puppet_modules': '/etc/puppet/modules',
            'puppet_options': '--logdest syslog ' \
                              '--logdest /var/log/puppet.log' \
                              '--trace --no-report',
            'report_dir': '/var/tmp/task_report',
            'pid_dir': '/var/tmp/task_run',
            'puppet_manifest': 'site.pp',
            'status_file': 'status',
            'debug': True,
            'task_file': 'task.yaml',
            'config_file': self.config_file,
            'log_file': '/var/log/tasklib.log'}

    @property
    def config(self):
        if self._config:
            return self._config
        default_config = self.default_config
        if self.config_file and os.path.exists(default_config['config_file']):
            with open(default_config['config_file']) as f:
                loaded = yaml.load(f.read())
            default_config.update(loaded)
        self._config = default_config
        return self._config

    def __getitem__(self, key):
        return self.config.get(key, None)

    def __setitem__(self, key, value):
        self._config[key] = value

    def __repr__(self):
        return yaml.dump(self.config, default_flow_style=False)
