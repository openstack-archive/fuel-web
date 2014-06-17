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

import yaml


def make_config_path(file_name):
    return os.path.join(os.path.dirname(__file__), file_name)


def read_yaml_config(path):
    return yaml.load(open(path, 'r'))


class Config(object):
    """Config object, returns None if field doesn't exist
    """

    def __init__(self, path):
        # NOTE(eli): initialize _config
        # with __setattr__ to prevent maximum
        # recursion depth exceeded error
        super(Config, self).__setattr__('_config', read_yaml_config(path))

    def __getattr__(self, name):
        return self._config.get(name, None)

    def __setattr__(self, name, value):
        self._config[name] = value


def build_config():
    """Builds config

    We cannot use plain yaml based config
    because our config consists of several files.

    This method generates additional properties
    for configuration data from config.yaml

    :returns: Config object
    """
    config = Config(make_config_path('config.yaml'))

    config.current_version = read_yaml_config(config.current_fuel_version_path)
    config.new_version = read_yaml_config(make_config_path('version.yaml'))
    config.astute = read_yaml_config(config.current_fuel_astute_path)

    return config
