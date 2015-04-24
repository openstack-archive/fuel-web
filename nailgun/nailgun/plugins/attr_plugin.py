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
import glob
import os

from distutils.version import StrictVersion
from urlparse import urljoin

import six
import yaml

from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.settings import settings


@six.add_metaclass(abc.ABCMeta)
class ClusterAttributesPluginBase(object):
    """Implements wrapper for plugin db model to provide
    logic related to configuration files.
    1. Uploading plugin provided cluster attributes
    2. Uploading tasks
    3. Enabling/Disabling of plugin based on cluster attributes
    4. Providing repositories/deployment scripts related info to clients
    """

    environment_config_name = 'environment_config.yaml'
    task_config_name = 'tasks.yaml'

    def __init__(self, plugin):
        self.plugin = plugin
        self.plugin_path = os.path.join(
            settings.PLUGINS_PATH,
            self.path_name)
        self.config_file = os.path.join(
            self.plugin_path,
            self.environment_config_name)
        self.tasks = []

    @abc.abstractmethod
    def path_name(self):
        """A name which is used to create path to
        plugin related scripts and repositories
        """

    def _load_config(self, config):
        if os.access(config, os.R_OK):
            with open(config, "r") as conf:
                return yaml.load(conf.read())
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

    def get_plugin_attributes(self, cluster):
        """Should be used for initial configuration uploading to
            custom storage. Will be invoked in 2 cases:
            1. Cluster is created but there was no plugins in system
            on that time, so when plugin is uploaded we need to iterate
            over all clusters and decide if plugin should be applied
            2. Plugins is uploaded before cluster creation, in this case
            we will iterate over all plugins and upload configuration for them

            In this case attributes will be added to same cluster attributes
            model and stored in editable field
        """
        config = {}
        if os.path.exists(self.config_file):
            config = self._load_config(self.config_file)
        if self.validate_cluster_compatibility(cluster):
            attrs = config.get("attributes", {})
            self.update_metadata(attrs)
            return {self.plugin.name: attrs}
        return {}

    def validate_cluster_compatibility(self, cluster):
        """Validates if plugin is compatible with cluster.
        - validates operating systems
        - modes of clusters (simple or ha)
        - release version
        """
        for release in self.plugin.releases:
            os_compat = (cluster.release.operating_system.lower()
                         == release['os'].lower())
            # plugin writer should be able to specify ha in release['mode']
            # and know nothing about ha_compact
            mode_compat = any(mode in cluster.mode for mode in release['mode'])
            release_version_compat = self._is_release_version_compatible(
                cluster.release.version, release['version'])
            if all((os_compat, mode_compat, release_version_compat)):
                return True
        return False

    def _is_release_version_compatible(self, rel_version, plugin_rel_version):
        """Checks if release version is compatible with
        plugin version.

        :param str rel_version: release version
        :param str plugin_rel_version: plugin release version
        :returns: True if compatible, Fals if not
        """
        rel_os, rel_fuel = rel_version.split('-')
        plugin_os, plugin_rel = plugin_rel_version.split('-')

        return rel_os.startswith(plugin_os) and rel_fuel.startswith(plugin_rel)

    def update_metadata(self, attributes):
        """Overwrights only default values in metadata.
        Plugin should be able to provide UI "native" conditions
        to enable/disable plugin on UI itself
        """
        attributes.setdefault('metadata', {})
        attributes['metadata'].update(self.default_metadata)
        return attributes

    @property
    def default_metadata(self):
        return {u'enabled': False, u'toggleable': True,
                u'weight': 70, u'label': self.plugin.title,
                'plugin_id': self.plugin.id}

    def set_cluster_tasks(self, cluster):
        """Loads plugins provided tasks from tasks config file and
        sets them to instance tasks variable.
        """
        task_yaml = os.path.join(
            self.plugin_path,
            self.task_config_name)
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
    def full_name(self):
        return u'{0}-{1}'.format(self.plugin.name, self.plugin.version)

    @property
    def slaves_scripts_path(self):
        return settings.PLUGINS_SLAVES_SCRIPTS_PATH.format(
            plugin_name=self.path_name)

    def get_release_info(self, release):
        """Returns plugin release information which corresponds to
            a provided release.
        """
        os = release.operating_system.lower()
        version = release.version

        release_info = filter(
            lambda r: (
                r['os'] == os and
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


class ClusterAttributesPluginV1(ClusterAttributesPluginBase):
    """Plugins attributes class for package version 1.0.0
    """

    @property
    def path_name(self):
        """Returns a name and full version, e.g. if there is
        a plugin with name "plugin_name" and version is "1.0.0",
        the method returns "plugin_name-1.0.0"
        """
        return self.full_name


class ClusterAttributesPluginV2(ClusterAttributesPluginBase):
    """Plugins attributes class for package version 2.0.0
    """

    @property
    def path_name(self):
        """Returns a name and major version of the plugin, e.g.
        if there is a plugin with name "plugin_name" and version
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
        """Returns major version of plugin's version, e.g.
        if plugin has 1.2.3 version, the method returns 1.2
        """
        version_tuple = StrictVersion(self.plugin.version).version
        major = '.'.join(map(str, version_tuple[:2]))

        return major


__version_mapping = {
    '1.0.': ClusterAttributesPluginV1,
    '2.0.': ClusterAttributesPluginV2
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
