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
from distutils.version import StrictVersion
import glob
import os
from urlparse import urljoin

import six

import loaders
import nailgun
from nailgun import consts
from nailgun import errors
from nailgun.logger import logger
from nailgun.settings import settings


@six.add_metaclass(abc.ABCMeta)
class PluginAdapterBase(object):
    """Implements wrapper for plugin db model configuration files logic

    1. Uploading plugin provided attributes
    2. Uploading tasks and deployment tasks
    3. Providing repositories/deployment scripts related info to clients
    """
    loader_class = loaders.PluginLoaderBase

    def __init__(self, plugin):
        self.plugin = plugin
        self.plugin_path = os.path.join(settings.PLUGINS_PATH, self.path_name)
        self.loader = self.loader_class(self.plugin_path)

    @property
    def attributes_processors(self):
        return {
            'attributes_metadata':
                lambda data: (data or {}).get('attributes', {}),
            'tasks': lambda data: data or []
        }

    @abc.abstractmethod
    def path_name(self):
        """A name which is used to create path to plugin scripts and repo"""

    def get_metadata(self):
        """Get plugin data tree.

        :return: All plugin metadata
        :rtype: dict
        """
        data_tree, report = self.loader.load()

        if report.is_failed():
            logger.error(report.render())
            logger.error('Problem with loading plugin {0}'.format(
                self.plugin_path))
            return data_tree

        for field in data_tree:
            if field in self.attributes_processors:
                data_tree[field] = \
                    self.attributes_processors[field](data_tree.get(field))

        data_tree = {
            k: v for k, v in six.iteritems(data_tree)
            if v is not None}

        return data_tree

    @property
    def plugin_release_versions(self):
        if not self.plugin.releases:
            return set()
        return set([rel['version'] for rel in self.plugin.releases])

    @property
    def title(self):
        return self.plugin.title

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
        return self.plugin.attributes_metadata

    @property
    def attributes_metadata(self):
        return self.get_attributes_metadata()

    def _add_defaults_to_task(self, task, roles_metadata):
        """Add required fault tolerance and cwd params to tasks.

        :param task: task
        :type task: dict
        :param roles_metadata: node roles metadata
        :type roles_metadata: dict

        :return: task
        :rtype: dict
        """
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
        return task

    def get_deployment_graph(self, graph_type=None):
        if graph_type is None:
            graph_type = consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE
        deployment_tasks = []
        graph_metadata = {}
        graph_instance = nailgun.objects.DeploymentGraph.get_for_model(
            self.plugin, graph_type)
        roles_metadata = self.plugin.roles_metadata
        if graph_instance:
            graph_metadata = nailgun.objects.DeploymentGraph.get_metadata(
                graph_instance)
            for task in nailgun.objects.DeploymentGraph.get_tasks(
                    graph_instance):
                deployment_tasks.append(
                    self._add_defaults_to_task(task, roles_metadata)
                )
        graph_metadata['tasks'] = deployment_tasks
        return graph_metadata

    def get_deployment_tasks(self, graph_type=None):
        return self.get_deployment_graph(graph_type)['tasks']

    def get_tasks(self):
        tasks = self.plugin.tasks
        slave_path = self.slaves_scripts_path
        for task in tasks:
            task['roles'] = task.get('role')

            parameters = task.get('parameters')
            if parameters is not None:
                parameters.setdefault('cwd', slave_path)

        return tasks

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
        """Get plugin release information which corresponds to given release.

        :returns: release info
        :rtype: dict
        """
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

        return urljoin(
            repo_base,
            release_info['repository_path']
        )

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

    loader_class = loaders.PluginLoaderV1

    @property
    def attributes_processors(self):
        ap = super(PluginAdapterV1, self).attributes_processors
        ap.update({
            'tasks': self._process_legacy_tasks
        })
        return ap

    @staticmethod
    def _process_legacy_tasks(tasks):
        if not tasks:
            return []

        for task in tasks:
            role = task['role']
            if isinstance(role, list) and 'controller' in role:
                role.append('primary-controller')
        return tasks

    def get_tasks(self):
        tasks = self.plugin.tasks
        slave_path = self.slaves_scripts_path
        for task in tasks:
            task['roles'] = task.get('role')

            role = task['role']
            if isinstance(role, list) \
                    and ('controller' in role) \
                    and ('primary-controller' not in role):
                role.append('primary-controller')

            parameters = task.get('parameters')
            if parameters is not None:
                parameters.setdefault('cwd', slave_path)
        return tasks

    @property
    def path_name(self):
        """Returns a name and full version

        e.g. if there is a plugin with name "plugin_name" and version
        is "1.0.0", the method returns "plugin_name-1.0.0"
        """
        return self.full_name


class PluginAdapterV2(PluginAdapterBase):
    """Plugins attributes class for package version 2.0.0"""

    loader_class = loaders.PluginLoaderV1

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

    loader_class = loaders.PluginLoaderV3

    def _process_deployment_tasks(self, deployment_tasks):
        dg = nailgun.objects.DeploymentGraph.get_for_model(
            self.plugin, graph_type=consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE)
        if dg:
            nailgun.objects.DeploymentGraph.update(
                dg, {'tasks': deployment_tasks})
        else:
            nailgun.objects.DeploymentGraph.create_for_model(
                {'tasks': deployment_tasks}, self.plugin)
        return deployment_tasks

    @property
    def attributes_processors(self):
        ap = super(PluginAdapterV3, self).attributes_processors
        ap.update({
            'deployment_tasks': self._process_deployment_tasks
        })
        return ap


class PluginAdapterV4(PluginAdapterV3):
    """Plugin wrapper class for package version 4.0.0"""

    loader_class = loaders.PluginLoaderV4


class PluginAdapterV5(PluginAdapterV4):
    """Plugin wrapper class for package version 5.0.0"""

    loader_class = loaders.PluginLoaderV5

    _release_fields_to_db_fields = {
        "attributes": "attributes_metadata",

        "networks": "networks_metadata",
        "network_roles": "network_roles_metadata",
        "volumes": "volumes_metadata",
        "roles": "roles_metadata",

        "components": "components_metadata",

        "os": "operating_system"
    }

    @property
    def attributes_processors(self):
        ap = super(PluginAdapterV5, self).attributes_processors
        ap.update({
            'releases': self._process_releases
        })
        return ap

    def _create_release_from_configuration(self, configuration):
        """Create templated release and graphs for given configuration.

        :param configuration:
        :return:
        """
        # deployment tasks not supposed for the release description
        # but we fix this developer mistake automatically

        # apply base template
        base_release = configuration.pop('base_release', None)
        if base_release:
            base_release.update(configuration)
            configuration = base_release

        configuration['state'] = consts.RELEASE_STATES.available

        #  remap fields
        for alias, name in six.iteritems(self._release_fields_to_db_fields):
            value = configuration.pop(alias, None)
            if value is not None:
                configuration[name] = value

        nailgun.objects.Release.create(configuration)

    def _process_releases(self, releases_records):
        """Split new release records from old-style release-deps records.

        :param releases_records: list of plugins and releases data
        :type releases_records: list

        :return: configurations that are extending existing
        :rtype: list
        """
        extend_releases = []
        for release in releases_records:
            is_basic_release = release.get('is_release', False)
            if is_basic_release:
                self._create_release_from_configuration(release)
            else:
                extend_releases.append(release)

        return extend_releases


class PluginAdapterV6(PluginAdapterV5):
    """Plugin wrapper class for package version 6.0.0"""

    loader_class = loaders.PluginLoaderV6

    @property
    def _release_fields_to_db_fields(self):
        fields = dict(super(PluginAdapterV6, self).
                      _release_fields_to_db_fields)
        fields['tags'] = 'tags_metadata'
        return fields


__plugins_mapping = {
    '1.0.': PluginAdapterV1,
    '2.0.': PluginAdapterV2,
    '3.0.': PluginAdapterV3,
    '4.0.': PluginAdapterV4,
    '5.0.': PluginAdapterV5,
    '6.0.': PluginAdapterV6
}


def get_supported_versions():
    return list(__plugins_mapping)


def get_adapter_for_package_version(plugin_version):
    """Get plugin adapter class for plugin version.

    :param plugin_version: plugin version string
    :type plugin_version: basestring|str

    :return: plugin loader class
    :rtype: loaders.PluginLoader|None
    """
    for plugin_version_head in __plugins_mapping:
        if plugin_version.startswith(plugin_version_head):
            return __plugins_mapping[plugin_version_head]


def wrap_plugin(plugin):
    """Creates plugin object with specific class version

    :param plugin: plugin db object
    :returns: cluster attribute object
    """
    package_version = plugin.package_version

    attr_class = get_adapter_for_package_version(package_version)

    if not attr_class:
        supported_versions = ', '.join(get_supported_versions())

        raise errors.PackageVersionIsNotCompatible(
            'Plugin id={0} package_version={1} '
            'is not supported by Nailgun, currently '
            'supported versions {2}'.format(
                plugin.id, package_version, supported_versions))

    return attr_class(plugin)
