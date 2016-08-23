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

import mapping

from nailgun.errors import errors
from nailgun.logger import logger

PLUGIN_ROOT_FILE = 'metadata.yaml'

PLUGIN_PACKAGE_VERSION_FIELD = 'package_version'


# self.plugin_path = os.path.join(settings.PLUGINS_PATH, self.path_name)

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

    :return:
    :rtype:
    """

    plugin_package_version = _get_package_version_from_path(plugin_path)

    loader_class = mapping.get_loader_for_package_version(
        plugin_package_version)
    adapter_class = mapping.get_adapter_for_package_version(
        plugin_package_version)

    if not loader_class or adapter_class:
        raise Exception('No such plugin package version: {}'.format(
            plugin_package_version))

    loader = loader_class(plugin_path)
    data, report = loader.load()
    if report.is_failed():
        raise Exception(report.render())
    else:
        pass
    # adapter = adapter_class()

    plugin_object = None
    return plugin_object
