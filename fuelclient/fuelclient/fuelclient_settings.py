# -*- coding: utf-8 -*-
#
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
import sys

import six
import yaml


_SETTINGS = None


def _parse_settings(config_file):
    """Returns parsed config file."""
    try:
        with open(config_file, 'r') as c_file:
            return yaml.load(c_file)
    except (IOError, yaml.YAMLError):
        six.print_('Cannot read settings file %s.\nPlease check that that '
                   'file exists, is a valid YAML file and you have all '
                   'required permissions for reading it' % config_file,
                   file=sys.stderr)
        sys.exit(1)


def _init_settings():
    global _SETTINGS

    # First read default settings
    project_path = os.path.dirname(__file__)
    default_config = os.path.join(project_path, 'settings.yaml')

    _SETTINGS = _parse_settings(default_config)

    # Update default settings from user's config file if any apicified
    custom_config = os.environ.get('FUELCLIENT_CUSTOM_SETTINGS')

    if custom_config:
        _SETTINGS.update(_parse_settings(custom_config))


def get_settings():
    """Retrieves settings for Fuel Client."""

    if not _SETTINGS:
        _init_settings()

    return _SETTINGS
