#    Copyright 2016 Mirantis, Inc.
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

import adapters
from nailgun import errors
from nailgun.logger import logger

PLUGIN_ROOT_FILE = 'metadata.yaml'

PLUGIN_PACKAGE_VERSION_FIELD = 'package_version'


def _get_package_version_from_path(plugin_path):
    config = os.path.join(plugin_path, PLUGIN_ROOT_FILE)
    if os.access(config, os.R_OK):
        with open(config, "r") as conf:
            try:
                return yaml.safe_load(conf.read()).get(
                    PLUGIN_PACKAGE_VERSION_FIELD)
            except yaml.YAMLError as exc:
                logger.warning(exc)
                raise errors.ParseError(
                    'Problem with loading YAML file {0}'.format(config))
    else:
        raise Exception("Config {0} is not readable.".format(config))


def sync(plugin_path):
    """Sync plugin data from given path.

    :param plugin_path: plugin folder path
    :type plugin_path: str|basestring

    :return: plugin object
    :rtype: models.Plugin
    """

    plugin_package_version = _get_package_version_from_path(plugin_path)

    adapter_class = adapters.get_adapter_for_package_version(
        plugin_package_version)
    if not adapter_class:
        raise Exception('No such plugin package version: {}'.format(
            plugin_package_version))
    adapter = adapter_class(plugin_path)
    data, report = adapter.load()
    if report.is_failed():
        raise Exception(report.render())
    else:
        pass

    plugin_object = None
    return plugin_object
