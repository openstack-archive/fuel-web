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


class Config(object):
    """Config object, returns None if field doesn't exist
    """

    def __init__(self):
        config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
        self.config = yaml.load(file(config_path, 'r'))

    def __getattr__(self, name):
        return self.config.get(name, None)

    def __repr__(self):
        self.config


config = Config()
