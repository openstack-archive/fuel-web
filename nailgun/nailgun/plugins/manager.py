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

import copy
import six
from six.moves import map

from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.objects.plugin import Plugin
from nailgun.objects.plugin import PluginCollection
from nailgun.plugins.adapters import wrap_plugin


class PluginManager(object):

    @classmethod
    def process_cluster_attributes(cls, cluster, attributes):
        """Generate Cluster-Plugins relation based on attributes

        Iterates through plugins attributes, creates
        or deletes Cluster <-> Plugins relation if plugin
        is enabled or disabled.

        :param cluster: A cluster instance
        :type cluster: nailgun.objects.cluster.Cluster
        :param attributes: Cluster attributes
        :type attributes: dict
        """
        def _convert_attrs(plugin_id, attrs):
            prefix = "#{0}_".format(plugin_id)
            result = dict((title[len(prefix):], attrs[title])
                          for title in attrs
                          if title.startswith(prefix))
            for attr in six.itervalues(result):
                if 'restrictions' not in attr:
                    continue
                if len(attr['restrictions']) == 1:
                    attr.pop('restrictions')
                else:
                    attr['restrictions'].pop()
            return result

        for attrs in six.itervalues(attributes):
            if not isinstance(attrs, dict):
                continue

            plugin_versions = attrs.pop('plugin_versions', None)
            if plugin_versions is None:
                continue

            metadata = attrs.pop('metadata', {})
            plugin_enabled = metadata.get('enabled', False)
            default = metadata.get('default', False)

            for version in plugin_versions['values']:
                pid = version.get('data')
                plugin = Plugin.get_by_uid(pid)
                if not plugin:
                    logger.warning(
                        'Plugin with id "%s" is not found, skip it', pid)
                    continue

                enabled = plugin_enabled and\
                    str(plugin.id) == plugin_versions['value']

                PluginCollection.set_attributes(
                    plugin.id, cluster.id, enabled=enabled,
                    attrs=_convert_attrs(plugin.id, attrs)
                    if enabled or default else None
                )

    @classmethod
    def get_plugins_attributes(cls, cluster):
        """Gets attributes of all plugins connected with given cluster.

        :param cluster: A cluster instance
        :type cluster: nailgun.objects.cluster.Cluster
        :return: Plugins attributes
        :rtype: dict
        """
        plugins_attributes = {}
        for pid, name, title, version, enabled, default_attrs, cluster_attrs\
                in PluginCollection.get_connected(cluster.id):
            data = plugins_attributes.get(name, {})
            metadata = data.setdefault('metadata', {
                u'toggleable': True,
                u'weight': 70
            })
            metadata.update({
                u'enabled': enabled or metadata.get('enabled', False),
                u'label': title,
            })
            data.update(cluster_attrs if enabled else {})
            plugins_attributes[name] = data

        return plugins_attributes

    @classmethod
    def get_plugins_attributes_with_versions(cls, cluster, default=False):
        """Gets attributes of all plugins connected with given cluster for UI.

        :param cluster: A cluster instance
        :type cluster: nailgun.objects.cluster.Cluster
        :param default: Need to return a default plugin's attributes or not
        :type default: bool
        :return: Plugins attributes
        :rtype: dict
        """
        plugins_attributes = {}
        versions = {
            u'type': u'radio',
            u'values': [],
            u'weight': 10,
            u'value': None,
            u'label': 'Choose a plugin version'
        }

        def _convert_attr(pid, name, title, attr):
            restrictions = attr.setdefault('restrictions', [])
            restrictions.append({
                'action': 'hide',
                'condition': "settings:{0}.plugin_versions.value != '{1}'"
                             .format(name, pid)
            })
            return "#{0}_{1}".format(pid, title), attr

        for pid, name, title, version, enabled, default_attrs, cluster_attrs\
                in PluginCollection.get_connected(cluster.id):
            enabled = enabled and not default
            data = plugins_attributes.get(name, {})
            metadata = data.setdefault('metadata', {
                u'toggleable': True,
                u'weight': 70
            })
            metadata.update({
                u'enabled': enabled or metadata.get('enabled', False),
                u'label': title,
                u'default': default
            })

            attrs = default_attrs if default else cluster_attrs
            data.update(_convert_attr(pid, name, key, attrs[key])
                        for key in attrs)

            if 'plugin_versions' in data:
                plugin_versions = data['plugin_versions']
            else:
                plugin_versions = copy.deepcopy(versions)

            plugin_versions['values'].append({
                u'data': str(pid),
                u'description': '',
                u'label': version
            })

            if not plugin_versions['value'] or enabled:
                plugin_versions['value'] = str(pid)

            data['plugin_versions'] = plugin_versions
            plugins_attributes[name] = data

        return plugins_attributes

    @classmethod
    def get_cluster_plugins_with_tasks(cls, cluster):
        cluster_plugins = []
        for plugin_db in PluginCollection.get_enabled(cluster.id):
            plugin_adapter = wrap_plugin(plugin_db)
            plugin_adapter.set_cluster_tasks()
            cluster_plugins.append(plugin_adapter)
        return cluster_plugins

    @classmethod
    def get_network_roles(cls, cluster):
        core_roles = cluster.release.network_roles_metadata
        known_roles = set(role['id'] for role in core_roles)

        plugin_roles = []
        conflict_roles = {}
        for plugin in PluginCollection.get_enabled(cluster.id):
            for role in plugin.network_roles_metadata:
                role_id = role['id']
                if role_id in known_roles:
                    conflict_roles[role_id] = plugin.name
                known_roles.add(role_id)
            plugin_roles.extend(plugin.network_roles_metadata)

        if conflict_roles:
            raise errors.NetworkRoleConflict(
                "Cannot override existing network roles: '{0}' in "
                "plugins: '{1}'".format(
                    ', '.join(conflict_roles),
                    ', '.join(set(conflict_roles.values()))))

        return plugin_roles

    @classmethod
    def get_plugins_deployment_tasks(cls, cluster):
        deployment_tasks = []
        processed_tasks = {}

        enabled_plugins = PluginCollection.get_enabled(cluster.id)
        for plugin_adapter in map(wrap_plugin, enabled_plugins):
            depl_tasks = plugin_adapter.deployment_tasks

            for t in depl_tasks:
                t_id = t['id']
                if t_id in processed_tasks:
                    raise errors.AlreadyExists(
                        'Plugin {0} is overlapping with plugin {1} '
                        'by introducing the same deployment task with '
                        'id {2}'
                        .format(plugin_adapter.full_name,
                                processed_tasks[t_id],
                                t_id)
                    )
                processed_tasks[t_id] = plugin_adapter.full_name

            deployment_tasks.extend(depl_tasks)

        return deployment_tasks

    @classmethod
    def get_plugins_node_roles(cls, cluster):
        result = {}
        core_roles = set(cluster.release.roles_metadata)

        for plugin_db in PluginCollection.get_enabled(cluster.id):
            plugin_roles = wrap_plugin(plugin_db).normalized_roles_metadata

            # we should check all possible cases of roles intersection
            # with core ones and those from other plugins
            # and afterwards show them in error message;
            # thus role names for which following checks
            # fails are accumulated in err_info variable
            err_roles = set()
            if set(plugin_roles) & core_roles:
                err_roles |= set(plugin_roles) & core_roles
            if set(plugin_roles) & set(result):
                err_roles |= set(plugin_roles) & set(result)

            if err_roles:
                raise errors.AlreadyExists(
                    "Plugin (ID={0}) is unable to register the following "
                    "node roles: {1}".format(plugin_db.id,
                                             ", ".join(err_roles))
                )

            # update info on processed roles in case of
            # success of all intersection checks
            result.update(plugin_roles)

        return result

    @classmethod
    def get_volumes_metadata(cls, cluster):
        """Get volumes metadata for cluster from all plugins which enabled it

        :param cluster: Cluster DB model
        :returns: dict -- object with merged volumes data from plugins
        """
        volumes_metadata = {
            'volumes': [],
            'volumes_roles_mapping': {}
        }
        release_volumes = cluster.release.volumes_metadata.get('volumes', [])
        release_volumes_ids = [v['id'] for v in release_volumes]
        processed_volumes = {}

        enabled_plugins = PluginCollection.get_enabled(cluster.id)
        for plugin_adapter in map(wrap_plugin, enabled_plugins):
            metadata = plugin_adapter.volumes_metadata

            for volume in metadata.get('volumes', []):
                volume_id = volume['id']
                if volume_id in release_volumes_ids:
                    raise errors.AlreadyExists(
                        'Plugin {0} is overlapping with release '
                        'by introducing the same volume with id "{1}"'
                        .format(plugin_adapter.full_name, volume_id))
                elif volume_id in processed_volumes:
                    raise errors.AlreadyExists(
                        'Plugin {0} is overlapping with plugin {1} '
                        'by introducing the same volume with id "{2}"'
                        .format(plugin_adapter.full_name,
                                processed_volumes[volume_id],
                                volume_id))

                processed_volumes[volume_id] = plugin_adapter.full_name

            volumes_metadata.get('volumes_roles_mapping', {}).update(
                metadata.get('volumes_roles_mapping', {}))
            volumes_metadata.get('volumes', []).extend(
                metadata.get('volumes', []))

        return volumes_metadata

    @classmethod
    def sync_plugins_metadata(cls, plugin_ids=None):
        """Sync metadata for plugins by given ids.

        If there are no ids all newest plugins will be synced
        """
        if plugin_ids:
            plugins = PluginCollection.get_by_uids(plugin_ids)
        else:
            plugins = PluginCollection.all()

        for plugin in plugins:
            plugin_adapter = wrap_plugin(plugin)
            plugin_adapter.sync_metadata_to_db()

    @classmethod
    def get_compatible_plugins(cls, cluster):
        """Returns a list of plugins that are compatible with a given cluster.

        :param cluster: A cluster instance
        :type cluster: nailgun.objects.cluster.Cluster
        :returns: A list of plugin instances
        """
        return list(six.moves.filter(
            lambda p: wrap_plugin(p).validate_cluster_compatibility(cluster),
            PluginCollection.all()))

    @classmethod
    def add_compatible_plugins(cls, cluster):
        """Populates 'cluster_plugins' table with compatible plugins.

        :param cluster: A cluster instance
        :type cluster: nailgun.objects.cluster.Cluster
        """
        for plugin in cls.get_compatible_plugins(cluster):
            PluginCollection.connect_to_cluster(
                plugin.id,
                cluster.id,
                plugin.attributes_metadata
            )
