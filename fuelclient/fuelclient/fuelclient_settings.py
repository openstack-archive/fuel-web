# -*- coding: utf-8 -*-

#    Copyright 2013-2014 Mirantis, Inc.
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

from fuelclient.cli import error


_SETTINGS = None


class FuelClientSettings(object):
    """Represents a model of Fuel Clients settings

    Default settigs file are distributed with the source code in
    the <DIST_DIR>/fuelclient_settings.yaml.

    User-specific settings may be stored in any YAML-formatted file
    the path to which should be supplied via the FUELCLIENT_CUSTOM_SETTINGS
    environment variable. Custom settins override the default ones.

    NOTE: This is not to be confused with the API client settings which
          requires a different configuration file.

    """
    def __init__(self):
        settings_files = []

        # Look up for a default file distributed with the source code
        project_path = os.path.dirname(__file__)
        project_settings_file = os.path.join(project_path,
                                             'fuelclient_settings.yaml')
        settings_files.append(project_settings_file)

        # Check whether a user specified a custom settings file
        test_config = os.environ.get('FUELCLIENT_CUSTOM_SETTINGS')
        if test_config:
            settings_files.append(test_config)

        self.config = {}
        for sf in settings_files:
            try:
                self._update_from_file(sf)
            except Exception as e:
                msg = ('Error while reading config file '
                       '%(file)s: %(err)s') % {'file': sf, 'err': str(e)}

                raise error.SettingsException(msg)

    def _update_from_file(self, path):
        with open(path, 'r') as custom_config:
            self.config.update(
                yaml.load(custom_config.read())
            )

    def dump(self):
        return yaml.dump(self.config)

    def __getattr__(self, name):
        return self.config.get(name, None)

    def __repr__(self):
        return '<settings object>'


def _init_settings():
    global _SETTINGS
    _SETTINGS = FuelClientSettings()


def get_settings():
    if _SETTINGS is None:
        _init_settings()

    return _SETTINGS
