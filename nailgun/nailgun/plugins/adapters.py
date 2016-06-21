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
from nailgun import errors
from nailgun.logger import logger
from nailgun.objects.deployment_graph import DeploymentGraph
from nailgun.settings import settings


@six.add_metaclass(abc.ABCMeta)
class PluginAdapterBase(object):
    """Implements wrapper for plugin db model configuration files logic

    1. Uploading plugin provided attributes
    2. Uploading tasks and deployment tasks
    3. Providing repositories/deployment scripts related info to clients
    """
    config_metadata = 'metadata.yaml'
    config_tasks = 'tasks.yaml'

    def __init__(self, plugin):
        self.plugin = plugin
        self._attributes_metadata = None
        self._tasks = None
        self.plugin_path = os.path.join(settings.PLUGINS_PATH, self.path_name)
        self.db_cfg_mapping = {
            'attributes_metadata': 'environment_config.yaml'
        }

    @abc.abstractmethod
    def path_name(self):
        """A name which is used to create path to plugin scripts and repos"""

    def get_metadata(self):
        """Get parsed plugin metadata from config yaml files.

        :return: All plugin metadata
        :rtype: dict
        """
        metadata = self._load_config(self.config_metadata) or {}
        metadata['tasks'] = self._load_tasks()

        for attribute, config in six.iteritems(self.db_cfg_mapping):
            attribute_data = self._load_config(config)
            # Plugin columns have constraints for nullable data,
            # so we need to check it
            if attribute_data is not None:
                if attribute == 'attributes_metadata':
                    attribute_data = attribute_data['attributes']
                metadata[attribute] = attribute_data

        return metadata

    def _load_config(self, file_name):
        config = os.path.join(self.plugin_path, file_name)
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

    def _load_tasks(self):
        return self._load_config(self.config_tasks) or []

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

    def get_attributes_metadata(self):
        if self._attributes_metadata is None:
            if self.plugin.attributes_metadata:
                self._attributes_metadata = self.plugin.attributes_metadata
            else:
                self._attributes_metadata = self._load_config(
                    'environment_config.yaml') or {}

        return self._attributes_metadata

    @property
    def attributes_metadata(self):
        return self.get_attributes_metadata()

    def get_deployment_tasks(self, graph_type=None):
        if graph_type is None:
            graph_type = consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE
        deployment_tasks = []
        graph_instance = DeploymentGraph.get_for_model(self.plugin, graph_type)
        roles_metadata = self.plugin.roles_metadata
        if graph_instance:
            for task in DeploymentGraph.get_tasks(graph_instance):
                if task.get('parameters'):
                    task['parameters'].setdefault(
                        'cwd', self.slaves_scripts_path)

                if task.get('type') == consts.ORCHESTRATOR_TASK_TYPES.group:
                    try:
                        task.setdefault(
                            'fault_tolerance',
                            roles_metadata[task['id']]['fault_tolerance']
                        )
                    except KeyError:
                        pass

                deployment_tasks.append(task)
        return deployment_tasks

    def get_tasks(self):
        if self._tasks is None:
            if self.plugin.tasks:
                self._tasks = self.plugin.tasks
            else:
                self._tasks = self._load_tasks()

            slave_path = self.slaves_scripts_path
            for task in self._tasks:
                task['roles'] = task['role']
                parameters = task.get('parameters')
                if parameters is not None:
                    parameters.setdefault('cwd', slave_path)

        return self._tasks

    @property
    def tasks(self):
        return self.get_tasks()

    @property
    def volumes_metadata(self):
        return self.plugin.volumes_metadata

    @property
    def components_metadata(self):
        return self.plugin.components_metadata

    @property
    def bond_attributes_metadata(self):
        return self.plugin.bond_attributes_metadata

    @property
    def nic_attributes_metadata(self):
        return self.plugin.nic_attributes_metadata

    @property
    def node_attributes_metadata(self):
        return self.plugin.node_attributes_metadata

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

    @staticmethod
    def _is_release_version_compatible(rel_version, plugin_rel_version):
        """Checks if release version is compatible with plugin version.

        :param rel_version: Release version
        :type rel_version: str
        :param plugin_rel_version: Plugin release version
        :type plugin_rel_version: str
        :return: True if compatible, False if not
        :rtype: bool
        """
        rel_os, rel_fuel = rel_version.split('-')
        plugin_os, plugin_rel = plugin_rel_version.split('-')

        return rel_os.startswith(plugin_os) and rel_fuel.startswith(plugin_rel)

    def validate_compatibility(self, cluster):
        """Validates if plugin is compatible with cluster.

        - validates operating systems
        - modes of clusters (simple or ha)
        - release version

        :param cluster: A cluster instance
        :type cluster: nailgun.db.sqlalchemy.models.cluster.Cluster
        :return: True if compatible, False if not
        :rtype: bool
        """
        cluster_os = cluster.release.operating_system.lower()
        for release in self.plugin.releases:
            if cluster_os != release['os'].lower():
                continue
            # plugin writer should be able to specify ha in release['mode']
            # and know nothing about ha_compact
            if not any(
                cluster.mode.startswith(mode) for mode in release['mode']
            ):
                continue

            if not self._is_release_version_compatible(
                cluster.release.version, release['version']
            ):
                continue
            return True
        return False

    def get_release_info(self, release):
        """Get plugin release information which corresponds to given release"""
        rel_os = release.operating_system.lower()
        version = release.version

        release_info = filter(
            lambda r: (
                r['os'] == rel_os and
                self._is_release_version_compatible(version, r['version'])),
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

    def _load_tasks(self):
        data = super(PluginAdapterV1, self)._load_tasks()
        for item in data:
            # backward compatibility for plugins added in version 6.0,
            # and it is expected that task with role: [controller]
            # will be executed on all controllers
            role = item['role']
            if (isinstance(role, list) and 'controller' in role):
                role.append('primary-controller')

        return data


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

    def __init__(self, plugin):
        super(PluginAdapterV3, self).__init__(plugin)
        self.db_cfg_mapping['network_roles_metadata'] = 'network_roles.yaml'
        self.db_cfg_mapping['roles_metadata'] = 'node_roles.yaml'
        self.db_cfg_mapping['volumes_metadata'] = 'volumes.yaml'

    def get_metadata(self, graph_type=None):
        dg = DeploymentGraph.get_for_model(self.plugin, graph_type)
        if dg:
            DeploymentGraph.update(
                dg,
                {'tasks': self._load_config('deployment_tasks.yaml')})
        else:
            DeploymentGraph.create_for_model(
                {'tasks': self._load_config('deployment_tasks.yaml')},
                self.plugin,
                graph_type)

        return super(PluginAdapterV3, self).get_metadata()


class PluginAdapterV4(PluginAdapterV3):
    """Plugin wrapper class for package version 4.0.0"""

    def __init__(self, plugin):
        super(PluginAdapterV4, self).__init__(plugin)
        self.db_cfg_mapping['components_metadata'] = 'components.yaml'


class PluginAdapterV5(PluginAdapterV4):
    """Plugin wrapper class for package version 5.0.0"""

    def __init__(self, plugin):
        super(PluginAdapterV5, self).__init__(plugin)
        self.db_cfg_mapping['nic_attributes_metadata'] = 'nic_config.yaml'
        self.db_cfg_mapping['bond_attributes_metadata'] = 'bond_config.yaml'
        self.db_cfg_mapping['node_attributes_metadata'] = 'node_config.yaml'


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
