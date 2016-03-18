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

import abc
import copy
import glob
import os

from distutils.version import StrictVersion
from urlparse import urljoin

import six
import yaml

from nailgun import consts
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.objects.deployment_graph import DeploymentGraph
from nailgun.objects.plugin import ClusterPlugins
from nailgun.objects.plugin import Plugin
from nailgun.settings import settings


@six.add_metaclass(abc.ABCMeta)
class PluginAdapterBase(object):
    """Implements wrapper for plugin db model configuration files logic

    1. Uploading plugin provided cluster attributes
    2. Uploading tasks
    3. Enabling/Disabling of plugin based on cluster attributes
    4. Providing repositories/deployment scripts related info to clients
    """

    environment_config_name = 'environment_config.yaml'
    plugin_metadata = 'metadata.yaml'
    task_config_name = 'tasks.yaml'

    def __init__(self, plugin):
        self.plugin = plugin
        self.plugin_path = os.path.join(
            settings.PLUGINS_PATH,
            self.path_name)
        self.tasks = []

    @abc.abstractmethod
    def path_name(self):
        """A name which is used to create path to plugin scripts and repos"""

    def sync_metadata_to_db(self):
        """Sync metadata from config yaml files into DB"""
        metadata_file_path = os.path.join(
            self.plugin_path, self.plugin_metadata)

        metadata = self._load_config(metadata_file_path) or {}
        Plugin.update(self.plugin, metadata)

    def _load_config(self, config):
        if os.access(config, os.R_OK):
            with open(config, "r") as conf:
                try:
                    return yaml.safe_load(conf.read())
                except yaml.YAMLError as exc:
                    logger.warning(exc)
                    raise errors.ParseError(
                        'Problem with loading YAML file {0}'.format(config))
        else:
            logger.warning("Config {0} is not readable.".format(config))

    def _load_tasks(self, config):
        data = self._load_config(config)
        for item in data:
            # backward compatibility for plugins added in version 6.0,
            # and it is expected that task with role: [controller]
            # will be executed on all controllers

            if (StrictVersion(self.plugin.package_version)
                    == StrictVersion('1.0')
                    and isinstance(item['role'], list)
                    and 'controller' in item['role']):
                item['role'].append('primary-controller')
        return data

    def set_cluster_tasks(self):
        """Load plugins provided tasks and set them to instance tasks variable

        Provided tasks are loaded from tasks config file.
        """
        task_yaml = os.path.join(
            self.plugin_path, self.task_config_name)
        if os.path.exists(task_yaml):
            self.tasks = self._load_tasks(task_yaml)

    def filter_tasks(self, tasks, stage):
        filtered = []
        for task in tasks:
            if stage and stage == task.get('stage'):
                filtered.append(task)
        return filtered

    @property
    def plugin_release_versions(self):
        if not self.plugin.releases:
            return set()
        return set([rel['version'] for rel in self.plugin.releases])

    @property
    def name(self):
        return self.plugin.name

    @property
    def full_name(self):
        return u'{0}-{1}'.format(self.plugin.name, self.plugin.version)

    @property
    def slaves_scripts_path(self):
        return settings.PLUGINS_SLAVES_SCRIPTS_PATH.format(
            plugin_name=self.path_name)

    def get_deployment_tasks(self, graph_type=None):
        if not graph_type:
            graph_type = consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE
        deployment_tasks = []
        graph_instance = DeploymentGraph.get_for_model(self.plugin, graph_type)
        if graph_instance:
            for task in DeploymentGraph.get_tasks(graph_instance):
                if task.get('parameters'):
                    task['parameters'].setdefault(
                        'cwd', self.slaves_scripts_path)
                deployment_tasks.append(task)
        return deployment_tasks

    # fixme(ikutukov): this getter only for default graph type, drop this
    # getter in future
    @property
    def deployment_tasks(self):
        return self.get_deployment_tasks()

    # it will better to replace to getters and setters
    @deployment_tasks.setter
    def deployment_tasks(self, value):
        if value:
            DeploymentGraph.upsert_for_model({'tasks': value}, self.plugin)

    @property
    def volumes_metadata(self):
        return self.plugin.volumes_metadata

    @property
    def components_metadata(self):
        return self.plugin.components_metadata

    @property
    def releases(self):
        return self.plugin.releases

    @property
    def normalized_roles_metadata(self):
        """Block plugin disabling if nodes with plugin-provided roles exist"""
        result = {}
        for role, meta in six.iteritems(self.plugin.roles_metadata):
            condition = "settings:{0}.metadata.enabled == false".format(
                self.plugin.name)
            meta = copy.copy(meta)
            meta['restrictions'] = [condition] + meta.get('restrictions', [])
            result[role] = meta

        return result

    def get_release_info(self, release):
        """Get plugin release information which corresponds to given release"""
        rel_os = release.operating_system.lower()
        version = release.version

        release_info = filter(
            lambda r: (
                r['os'] == rel_os and
                ClusterPlugins.is_release_version_compatible(version,
                                                             r['version'])),
            self.plugin.releases)

        return release_info[0]

    def repo_files(self, cluster):
        release_info = self.get_release_info(cluster.release)
        repo_path = os.path.join(
            settings.PLUGINS_PATH,
            self.path_name,
            release_info['repository_path'],
            '*')
        return glob.glob(repo_path)

    def repo_url(self, cluster):
        release_info = self.get_release_info(cluster.release)
        repo_base = settings.PLUGINS_REPO_URL.format(
            master_ip=settings.MASTER_IP,
            plugin_name=self.path_name)

        return urljoin(repo_base, release_info['repository_path'])

    def master_scripts_path(self, cluster):
        release_info = self.get_release_info(cluster.release)
        # NOTE(eli): we cannot user urljoin here, because it
        # works wrong, if protocol is rsync
        base_url = settings.PLUGINS_SLAVES_RSYNC.format(
            master_ip=settings.MASTER_IP,
            plugin_name=self.path_name)
        return '{0}{1}'.format(
            base_url,
            release_info['deployment_scripts_path'])


class PluginAdapterV1(PluginAdapterBase):
    """Plugins attributes class for package version 1.0.0"""

    @property
    def path_name(self):
        """Returns a name and full version

        e.g. if there is a plugin with name "plugin_name" and version
        is "1.0.0", the method returns "plugin_name-1.0.0"
        """
        return self.full_name


class PluginAdapterV2(PluginAdapterBase):
    """Plugins attributes class for package version 2.0.0"""

    @property
    def path_name(self):
        """Returns a name and major version of the plugin

        e.g. if there is a plugin with name "plugin_name" and version
        is "1.0.0", the method returns "plugin_name-1.0".

        It's different from previous version because in previous
        version we did not have plugin updates, in 2.0.0 version
        we should expect different plugin path.

        See blueprint: https://blueprints.launchpad.net/fuel/+spec
                              /plugins-security-fixes-delivery
        """
        return u'{0}-{1}'.format(self.plugin.name, self._major_version)

    @property
    def _major_version(self):
        """Returns major version of plugin's version

        e.g. if plugin has 1.2.3 version, the method returns 1.2
        """
        version_tuple = StrictVersion(self.plugin.version).version
        major = '.'.join(map(str, version_tuple[:2]))

        return major


class PluginAdapterV3(PluginAdapterV2):
    """Plugin wrapper class for package version 3.0.0"""

    node_roles_config_name = 'node_roles.yaml'
    volumes_config_name = 'volumes.yaml'
    deployment_tasks_config_name = 'deployment_tasks.yaml'
    network_roles_config_name = 'network_roles.yaml'

    def sync_metadata_to_db(self):
        """Sync metadata from all config yaml files to DB"""
        super(PluginAdapterV3, self).sync_metadata_to_db()

        db_config_metadata_mapping = {
            'attributes_metadata': self.environment_config_name,
            'roles_metadata': self.node_roles_config_name,
            'volumes_metadata': self.volumes_config_name,
            'network_roles_metadata': self.network_roles_config_name,
            'tasks': self.task_config_name
        }

        self._update_plugin(db_config_metadata_mapping)

    def _update_plugin(self, mapping):
        data_to_update = {}

        for attribute, config in six.iteritems(mapping):
            config_file_path = os.path.join(self.plugin_path, config)
            attribute_data = self._load_config(config_file_path)
            # Plugin columns have constraints for nullable data, so
            # we need to check it
            if attribute_data:
                if attribute == 'attributes_metadata':
                    attribute_data = attribute_data['attributes']
                data_to_update[attribute] = attribute_data

        Plugin.update(self.plugin, data_to_update)

        # update deployment tasks
        deployment_tasks_file_path = os.path.join(
            self.plugin_path,
            self.deployment_tasks_config_name)
        deployment_tasks_data = self._load_config(deployment_tasks_file_path)
        if deployment_tasks_data:
            # fixme(ikutukov) rework to getters and setters to be able to
            # change deployment graph type
            self.deployment_tasks = deployment_tasks_data


class PluginAdapterV4(PluginAdapterV3):
    """Plugin wrapper class for package version 4.0.0"""

    components = 'components.yaml'

    def sync_metadata_to_db(self):
        super(PluginAdapterV4, self).sync_metadata_to_db()

        db_config_metadata_mapping = {
            'components_metadata': self.components
        }

        self._update_plugin(db_config_metadata_mapping)


class PluginAdapterV5(PluginAdapterV4):
    """Plugin wrapper class for package version 5.0.0"""


__version_mapping = {
    '1.0.': PluginAdapterV1,
    '2.0.': PluginAdapterV2,
    '3.0.': PluginAdapterV3,
    '4.0.': PluginAdapterV4,
    '5.0.': PluginAdapterV5,
}


def wrap_plugin(plugin):
    """Creates plugin object with specific class version

    :param plugin: plugin db object
    :returns: cluster attribute object
    """
    package_version = plugin.package_version

    attr_class = None

    # Filter by major version
    for version, klass in six.iteritems(__version_mapping):
        if package_version.startswith(version):
            attr_class = klass
            break

    if not attr_class:
        supported_versions = ', '.join(__version_mapping.keys())

        raise errors.PackageVersionIsNotCompatible(
            'Plugin id={0} package_version={1} '
            'is not supported by Nailgun, currently '
            'supported versions {2}'.format(
                plugin.id, package_version, supported_versions))

    return attr_class(plugin)
