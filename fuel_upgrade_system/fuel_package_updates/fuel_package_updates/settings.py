#!/usr/bin/env python
#    Copyright 2015 Mirantis, Inc.
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

FUEL_SETTINGS_VAR = 'FUEL_PACKAGE_UPDATES_SETTINGS_PATH'
DEFAULT_SETTINGS_PATH = os.path.join(os.path.dirname(__file__),
                                     'settings.yaml')
LOGGER_NAME = 'fuel_package_updates'


class Settings(object):

    def __init__(self, **kwargs):
        self._settings = kwargs

    def __getattr__(self, name):
        if name in self._settings:
            return self._settings[name]
        return super(Settings, self).__getattribute__(name)

    @staticmethod
    def yaml_load(path):
        with open(path) as f:
            settings = yaml.load(f)
        return settings

    @classmethod
    def from_yaml(cls, path):
        return cls(**cls.yaml_load(path))

    def update_from_yaml(self, path):
        self._settings.update(self.yaml_load(path))


SETTINGS = Settings.from_yaml(DEFAULT_SETTINGS_PATH)

custom_settings_path = os.getenv(FUEL_SETTINGS_VAR)
if custom_settings_path:
    SETTINGS.update_from_yaml(custom_settings_path)
