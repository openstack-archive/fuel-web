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

    def __init__(self):
        self._config = {}

    @property
    def default_config(self):
        curdir = os.getcwd()
        return {
            'library_dir': os.path.join(curdir, 'library'),
            'task_dir': curdir,
            'module_dir': '/etc/puppet/modules',
            'puppet_options': '',
            'report_format': 'xunit',
            'report_extension': 'xml',
            'report_dir': '/tmp/task_report',
            'pid_dir': '/tmp/task_run',
            'puppet_manifest': 'site.pp',
            'spec_pre': 'spec/pre_spec.rb',
            'spec_post': 'spec/post_spec.rb',
            'debug': False,
            'task_file': 'task.yaml',
            'config_file': os.path.join(curdir, 'etc', 'config.yaml')}

    @property
    def config(self):
        if self._config:
            return self._config
        default_config = self.default_config
        if os.path.exists(default_config['config_file']):
            with open(default_config['config_file']) as f:
                self._config = yaml.load(f.read())
            return self._config
        return default_config

    def __getitem__(self, method_name):
        return self.config[method_name]

    def __repr__(self):
        return yaml.dump(self.config, default_flow_style=False)
