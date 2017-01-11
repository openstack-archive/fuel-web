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
import io
import os
import yaml


from distutils.version import StrictVersion

import six
from six.moves import map

from adapters import wrap_plugin
from nailgun import consts
from nailgun import errors
from nailgun.logger import logger
from nailgun.objects.plugin import ClusterPlugin
from nailgun.objects.plugin import NodeBondInterfaceClusterPlugin
from nailgun.objects.plugin import NodeClusterPlugin
from nailgun.objects.plugin import NodeNICInterfaceClusterPlugin
from nailgun.objects.plugin import Plugin
from nailgun.objects.plugin import PluginCollection
from nailgun.settings import settings
from nailgun.utils import dict_merge
from nailgun.utils import dict_update
from nailgun.utils import get_in


class PluginManager(object):
    @classmethod
    def contains_legacy_tasks(cls, plugin):
        if plugin.tasks:
            return True
        min_task_version = StrictVersion(consts.TASK_CROSS_DEPENDENCY)
        for task in plugin.get_deployment_tasks():
            task_version = StrictVersion(task.get('version', '0.0.0'))
            if (task.get('type') not in consts.INTERNAL_TASKS
                    and task_version < min_task_version):
                return True
        return False

    @classmethod
    def process_cluster_attributes(cls, cluster, attributes):
        """Generate Cluster-Plugins relation based on attributes.

        Iterates through plugins attributes, creates
        or deletes Cluster <-> Plugins relation if plugin
        is enabled or disabled.

        :param cluster: A cluster instance
        :type cluster: nailgun.db.sqlalchemy.models.cluster.Cluster
        :param attributes: Cluster attributes
        :type attributes: dict
        """
        from nailgun.objects import Release

        plugins = {}

        # Detach plugins data
        for k in list(attributes):
            if cls.is_plugin_data(attributes[k]):
                plugins[k] = attributes.pop(k)['metadata']

        propagate_task_deploy = get_in(
            attributes, 'common', 'propagate_task_deploy', 'value')
        if propagate_task_deploy is not None:
            legacy_tasks_are_ignored = not propagate_task_deploy
        else:
            legacy_tasks_are_ignored = not get_in(
                cluster.attributes.editable,
                'common', 'propagate_task_deploy', 'value')

        for container in six.itervalues(plugins):
            default = container.get('default', False)
            for attrs in container.get('versions', []):
                version_metadata = attrs.pop('metadata')
                plugin_id = version_metadata['plugin_id']
                plugin = Plugin.get_by_uid(plugin_id)
                if not plugin:
                    logger.warning(
                        'Plugin with id "%s" is not found, skip it', plugin_id)
                    continue
                enabled = container['enabled'] \
                    and plugin_id == container['chosen_id']
                if (enabled and
                        Release.is_lcm_supported(cluster.release) and
                        legacy_tasks_are_ignored and
                        cls.contains_legacy_tasks(
                            wrap_plugin(Plugin.get_by_uid(plugin.id)))):
                    raise errors.InvalidData(
                        'Cannot enable plugin with legacy tasks unless '
                        'propagate_task_deploy attribute is set. '
                        'Ensure tasks.yaml is empty and all tasks '
                        'has version >= 2.0.0.')
                ClusterPlugin.set_attributes(
                    cluster.id, plugin.id, enabled=enabled,
                    attrs=attrs if enabled or default else None
                )

    @classmethod
    def get_plugins_attributes(
            cls, cluster, all_versions=False, default=False):
        """Gets attributes of all plugins connected with given cluster.

        :param cluster: A cluster instance
        :type cluster: nailgun.db.sqlalchemy.models.cluster.Cluster
        :param all_versions: True to get attributes of all versions of plugins
        :type all_versions: bool
        :param default: True to return a default plugins attributes (for UI)
        :type default: bool
        :return: Plugins attributes
        :rtype: dict
        """
        plugins_attributes = {}
        for plugin in ClusterPlugin.get_connected_plugins_data(cluster.id):
            db_plugin = Plugin.get_by_uid(plugin.id)
            plugin_adapter = wrap_plugin(db_plugin)
            default_attrs = plugin_adapter.attributes_metadata

            if all_versions:
                container = plugins_attributes.setdefault(plugin.name, {})
                enabled = plugin.enabled and not (all_versions and default)
                cls.create_common_metadata(plugin, container, enabled)
                container['metadata']['default'] = default

                versions = container['metadata'].setdefault('versions', [])
                if default:
                    actual_attrs = copy.deepcopy(default_attrs)
                    actual_attrs.setdefault('metadata', {})
                else:
                    actual_attrs = copy.deepcopy(plugin.attributes)
                    actual_attrs['metadata'] = default_attrs.get('metadata',
                                                                 {})
                actual_attrs['metadata']['contains_legacy_tasks'] = \
                    cls.contains_legacy_tasks(plugin_adapter)
                cls.fill_plugin_metadata(plugin, actual_attrs['metadata'])
                versions.append(actual_attrs)

                container['metadata'].setdefault('chosen_id', plugin.id)
                if enabled:
                    container['metadata']['chosen_id'] = plugin.id

            elif plugin.enabled:
                container = plugins_attributes.setdefault(plugin.name, {})
                cls.create_common_metadata(plugin, container)
                container['metadata'].update(default_attrs.get('metadata', {}))
                cls.fill_plugin_metadata(plugin, container['metadata'])
                container.update(plugin.attributes)

        return plugins_attributes

    @classmethod
    def inject_plugin_attribute_values(cls, attributes):
        """Inject given attributes with plugin attributes values.

        :param attributes: Cluster attributes
        :type attributes: dict
        """
        for k, attrs in six.iteritems(attributes):
            if (not cls.is_plugin_data(attrs) or
                    not attrs['metadata']['enabled']):
                continue
            metadata = attrs['metadata']
            selected_plugin_attrs = cls._get_specific_version(
                metadata.get('versions', []),
                metadata.get('chosen_id'))
            selected_plugin_attrs.pop('metadata', None)

            dict_update(attrs, selected_plugin_attrs, 1)

    @classmethod
    def is_plugin_data(cls, attributes):
        """Looking for a plugins hallmark.

        :param attributes: Item of editable attributes of cluster
        :type attributes: dict
        :return: True if it's a plugins container
        :rtype: bool
        """
        return attributes.get('metadata', {}).get('class') == 'plugin'

    @classmethod
    def create_common_metadata(cls, plugin, attributes, enabled=None):
        """Create common metadata attribute for all versions of plugin.

        :param plugin: A plugin instance
        :type plugin: nailgun.db.sqlalchemy.models.plugins.Plugin
        :param attributes: Common attributes of plugin versions
        :type attributes: dict
        :param enabled: Plugin status
        :type enabled: bool
        """
        metadata = attributes.setdefault('metadata', {
            'class': 'plugin',
            'toggleable': True,
            'weight': 70
        })
        metadata['label'] = plugin.title
        if enabled is None:
            enabled = plugin.enabled
        metadata['enabled'] = enabled or metadata.get('enabled', False)

    @classmethod
    def fill_plugin_metadata(cls, plugin, metadata):
        """Fill a plugin's metadata attribute.

        :param plugin: A plugin instance
        :type plugin: nailgun.db.sqlalchemy.models.plugins.Plugin
        :param metadata: Plugin metadata
        :type metadata: dict
        """
        metadata['plugin_id'] = plugin.id
        metadata['plugin_version'] = plugin.version
        metadata['hot_pluggable'] = plugin.is_hotpluggable

    @classmethod
    def get_enabled_plugins(cls, cluster):
        return [wrap_plugin(plugin)
                for plugin in ClusterPlugin.get_enabled(cluster.id)]

    @classmethod
    def get_network_roles(cls, cluster, merge_policy):
        """Returns the network roles from plugins.

        The roles cluster and plugins will be mixed
        according to merge policy.
        """

        instance_roles = cluster.release.network_roles_metadata
        all_roles = dict((role['id'], role) for role in instance_roles)
        conflict_roles = dict()

        for plugin in ClusterPlugin.get_enabled(cluster.id):
            for role in plugin.network_roles_metadata:
                role_id = role['id']
                if role_id in all_roles:
                    try:
                        merge_policy.apply_patch(
                            all_roles[role_id],
                            role
                        )
                    except errors.UnresolvableConflict as e:
                        logger.error("cannot merge plugin {0}: {1}"
                                     .format(plugin.name, e))
                        conflict_roles[role_id] = plugin.name
                else:
                    all_roles[role_id] = role

        if conflict_roles:
            raise errors.NetworkRoleConflict(
                "Cannot override existing network roles: '{0}' in "
                "plugins: '{1}'".format(
                    ', '.join(conflict_roles),
                    ', '.join(set(conflict_roles.values()))))

        return list(all_roles.values())

    @classmethod
    def get_plugins_deployment_graph(cls, cluster, graph_type=None):
        deployment_tasks = []
        processed_tasks = {}

        enabled_plugins = ClusterPlugin.get_enabled(cluster.id)
        graph_metadata = {}
        for plugin_adapter in map(wrap_plugin, enabled_plugins):
            depl_graph = plugin_adapter.get_deployment_graph(graph_type)
            depl_tasks = depl_graph.pop('tasks')
            dict_update(graph_metadata, depl_graph)

            for t in depl_tasks:
                t_id = t['id']
                if t_id in processed_tasks:
                    raise errors.AlreadyExists(
                        'Plugin {0} is overlapping with plugin {1} '
                        'by introducing the same deployment task with '
                        'id {2}'.format(
                            plugin_adapter.full_name,
                            processed_tasks[t_id],
                            t_id
                        )
                    )
                processed_tasks[t_id] = plugin_adapter.full_name

            deployment_tasks.extend(depl_tasks)
        graph_metadata['tasks'] = deployment_tasks
        return graph_metadata

    @classmethod
    def get_plugins_deployment_tasks(cls, cluster, graph_type=None):
        return cls.get_plugins_deployment_graph(cluster, graph_type)['tasks']

    @classmethod
    def get_plugins_node_roles(cls, cluster):
        result = {}
        core_roles = set(cluster.release.roles_metadata)

        for plugin_db in ClusterPlugin.get_enabled(cluster.id):
            plugin_roles = wrap_plugin(plugin_db).normalized_roles_metadata

            # we should check all possible cases of roles intersection
            # with core ones and those from other plugins
            # and afterwards show them in error message;
            # thus role names for which following checks
            # fails are accumulated in err_info variable
            err_roles = set(
                r for r in plugin_roles if r in core_roles or r in result
            )
            if err_roles:
                raise errors.AlreadyExists(
                    "Plugin (ID={0}) is unable to register the following "
                    "node roles: {1}".format(plugin_db.id,
                                             ", ".join(sorted(err_roles)))
                )

            # update info on processed roles in case of
            # success of all intersection checks
            result.update(plugin_roles)

        return result

    @classmethod
    def get_tags_metadata(cls, cluster):
        """Get tags metadata for all plugins enabled for the cluster

        :param cluster: A cluster instance
        :type cluster: Cluster model
        :return: dict -- Object with merged tags data from plugins
        """
        tags_metadata = {}
        enabled_plugins = ClusterPlugin.get_enabled(cluster.id)
        for plugin in enabled_plugins:
            tags_metadata.update(plugin.tags_metadata)
        return tags_metadata

    @classmethod
    def get_volumes_metadata(cls, cluster):
        """Get volumes metadata for all plugins enabled for the cluster

        :param cluster: A cluster instance
        :type cluster: Cluster model
        :return: dict -- Object with merged volumes data from plugins
        """
        def _get_volumes_ids(instance):
            return [v['id']
                    for v in instance.volumes_metadata.get('volumes', [])]

        volumes_metadata = {
            'volumes': [],
            'volumes_roles_mapping': {},
            'rule_to_pick_boot_disk': [],
        }

        cluster_volumes_ids = _get_volumes_ids(cluster)
        release_volumes_ids = _get_volumes_ids(cluster.release)
        processed_volumes = {}

        enabled_plugins = ClusterPlugin.get_enabled(cluster.id)
        for plugin_adapter in map(wrap_plugin, enabled_plugins):
            metadata = plugin_adapter.volumes_metadata

            for volume in metadata.get('volumes', []):
                volume_id = volume['id']
                for owner, volumes_ids in (('cluster', cluster_volumes_ids),
                                           ('release', release_volumes_ids)):
                    if volume_id in volumes_ids:
                        raise errors.AlreadyExists(
                            'Plugin {0} is overlapping with {1} '
                            'by introducing the same volume with '
                            'id "{2}"'.format(plugin_adapter.full_name,
                                              owner,
                                              volume_id)
                        )
                    elif volume_id in processed_volumes:
                        raise errors.AlreadyExists(
                            'Plugin {0} is overlapping with plugin {1} '
                            'by introducing the same volume with '
                            'id "{2}"'.format(
                                plugin_adapter.full_name,
                                processed_volumes[volume_id],
                                volume_id
                            )
                        )

                processed_volumes[volume_id] = plugin_adapter.full_name

            volumes_metadata.get('volumes_roles_mapping', {}).update(
                metadata.get('volumes_roles_mapping', {}))
            volumes_metadata.get('volumes', []).extend(
                metadata.get('volumes', []))
            volumes_metadata.get('rule_to_pick_boot_disk', []).extend(
                metadata.get('rule_to_pick_boot_disk', []))

        return volumes_metadata

    @classmethod
    def get_components_metadata(cls, release):
        """Get components metadata for all plugins which related to release.

        :param release: A release instance
        :type release: Release model
        :return: list -- List of plugins components
        """
        components = []
        seen_components = \
            dict((c['name'], 'release') for c in release.components_metadata)

        for plugin_adapter in map(
                wrap_plugin, PluginCollection.get_by_release(release)):
            plugin_name = plugin_adapter.name
            for component in plugin_adapter.components_metadata:
                name = component['name']
                if seen_components.get(name, plugin_name) != plugin_name:
                    raise errors.AlreadyExists(
                        'Plugin {0} is overlapping with {1} by introducing '
                        'the same component with name "{2}"'.format(
                            plugin_adapter.name,
                            seen_components[name],
                            name
                        )
                    )

                if name not in seen_components:
                    seen_components[name] = plugin_adapter.name
                    components.append(component)

        return components

    @classmethod
    def get_plugins_node_default_attributes(cls, cluster):
        """Get node attributes metadata for enabled plugins of the cluster.

        :param cluster: A cluster instance
        :type cluster: models.Cluster
        :returns: dict -- Object with node attributes
        """
        plugins_node_metadata = {}
        enabled_plugins = ClusterPlugin.get_enabled(cluster.id)
        for plugin_adapter in map(wrap_plugin, enabled_plugins):
            metadata = plugin_adapter.node_attributes_metadata
            # TODO(ekosareva): resolve conflicts of same attribute names
            #                  for different plugins
            plugins_node_metadata.update(metadata)

        return plugins_node_metadata

    @classmethod
    def get_plugin_node_attributes(cls, node):
        """Return plugin related attributes for Node.

        :param node: A Node instance
        :type node: models.Node
        :returns: dict object with plugin Node attributes
        """
        return NodeClusterPlugin.get_all_enabled_attributes_by_node(node)

    @classmethod
    def update_plugin_node_attributes(cls, attributes):
        """Update plugin related node attributes.

        :param attributes: new attributes data
        :type attributes: dict
        :returns: None
        """
        plugins_attributes = {}
        for k in list(attributes):
            if cls.is_plugin_data(attributes[k]):
                attribute_data = attributes.pop(k)
                attribute_data['metadata'].pop('class')
                node_plugin_id = \
                    attribute_data['metadata'].pop('node_plugin_id')
                plugins_attributes.setdefault(
                    node_plugin_id, {}).update({k: attribute_data})

        # TODO(ekosareva): think about changed metadata or sections set
        for plugin_id, plugin_attributes in six.iteritems(plugins_attributes):
            NodeClusterPlugin.set_attributes(
                plugin_id,
                plugin_attributes
            )

    @classmethod
    def add_plugin_attributes_for_node(cls, node):
        """Add plugin related attributes for Node.

        :param node: A Node instance
        :type node: models.Node
        :returns: None
        """
        NodeClusterPlugin.add_cluster_plugins_for_node(node)

    @classmethod
    def get_bond_default_attributes(cls, cluster):
        """Get plugin bond attributes metadata for cluster.

        :param cluster: A cluster instance
        :type cluster: Cluster model
        :returns: dict -- Object with bond attributes
        """
        plugins_bond_metadata = {}
        enabled_plugins = ClusterPlugin.get_enabled(cluster.id)
        for plugin_adapter in six.moves.map(wrap_plugin, enabled_plugins):
            metadata = plugin_adapter.bond_attributes_metadata
            if metadata:
                metadata = dict_merge({
                    'metadata': {
                        'label': plugin_adapter.title, 'class': 'plugin'}},
                    metadata)
                plugins_bond_metadata[plugin_adapter.name] = metadata

        return plugins_bond_metadata

    @classmethod
    def get_bond_attributes(cls, bond):
        """Return plugin related attributes for Bond.

        :param interface: A BOND instance
        :type interface: Bond model
        """
        return NodeBondInterfaceClusterPlugin.\
            get_all_enabled_attributes_by_bond(bond)

    @classmethod
    def add_plugin_attributes_for_bond(cls, bond):
        """Add plugin related attributes for Bond.

        :param interface: A BOND instance
        :type interface: Bond model
        :returns: object -- Bond model instance
        """
        NodeBondInterfaceClusterPlugin.\
            add_cluster_plugins_for_node_bond(bond)

        return bond

    @classmethod
    def update_bond_attributes(cls, attributes):
        plugins = []
        for k in list(attributes):
            if cls.is_plugin_data(attributes[k]):
                plugins.append(attributes.pop(k))

        for plugin in plugins:
            metadata = plugin.get('metadata', {})
            bond_plugin_id = metadata.pop('bond_plugin_id')
            NodeBondInterfaceClusterPlugin.\
                set_attributes(bond_plugin_id, plugin)

    @classmethod
    def get_nic_default_attributes(cls, cluster):
        """Get default plugin nic attributes for cluster.

        :param cluster: A cluster instance
        :type cluster: Cluster model
        :returns: dict -- Object with nic attributes
        """
        plugins_nic_metadata = {}
        enabled_plugins = ClusterPlugin.get_enabled(cluster.id)
        for plugin_adapter in six.moves.map(wrap_plugin, enabled_plugins):
            metadata = plugin_adapter.nic_attributes_metadata
            if metadata:
                metadata = dict_merge({
                    'metadata': {
                        'label': plugin_adapter.title, 'class': 'plugin'}},
                    metadata)
                plugins_nic_metadata[plugin_adapter.name] = metadata

        return plugins_nic_metadata

    @classmethod
    def get_nic_attributes(cls, interface):
        """Return plugin related attributes for NIC.

        :param interface: A NIC instance
        :type interface: Interface model
        :returns:
        """
        return NodeNICInterfaceClusterPlugin.\
            get_all_enabled_attributes_by_interface(interface)

    @classmethod
    def update_nic_attributes(cls, attributes):
        plugins = []
        for k in list(attributes):
            if cls.is_plugin_data(attributes[k]):
                plugins.append(attributes.pop(k))

        for plugin in plugins:
            metadata = plugin.get('metadata', {})
            nic_plugin_id = metadata.pop('nic_plugin_id')
            NodeNICInterfaceClusterPlugin.\
                set_attributes(nic_plugin_id, plugin)

    @classmethod
    def add_plugin_attributes_for_interface(cls, interface):
        """Add plugin related attributes for NIC.

        :param interface: A NIC instance
        :type interface: Interface model
        :returns: None
        """
        NodeNICInterfaceClusterPlugin.\
            add_cluster_plugins_for_node_nic(interface)

    @classmethod
    def sync_plugins_metadata(cls, plugin_ids=None):
        """Sync or install metadata for plugins by given IDs.

        If there are no IDs, all plugins will be synced.

        :param plugin_ids: list of plugin IDs
        :type plugin_ids: list
        """
        if plugin_ids:
            for plugin in PluginCollection.get_by_uids(plugin_ids):
                cls._plugin_update(plugin)
        else:
            cls._install_or_update_or_delete_plugins()

    @classmethod
    def _install_or_update_or_delete_plugins(cls):
        """Sync plugins using FS and DB.

        If plugin:
            in DB and present on filesystem, it will be updated;
            in DB and not present on filesystem, it will be removed;
            not in DB, but present on filesystem, it will be installed
        """
        installed_plugins = {}
        for plugin in PluginCollection.all():
            plugin_adapter = wrap_plugin(plugin)
            installed_plugins[plugin_adapter.path_name] = plugin

        for plugin_dir in cls._list_plugins_on_fs():
            if plugin_dir in installed_plugins:
                cls._plugin_update(installed_plugins.pop(plugin_dir))
            else:
                cls._plugin_create(plugin_dir)
        for deleted_plugin in installed_plugins.values():
            cls._plugin_delete(deleted_plugin)

    @classmethod
    def _plugin_update(cls, plugin):
        """Update plugin metadata.

        :param plugin: A plugin instance
        :type plugin: plugin model
        """
        try:
            plugin_adapter = wrap_plugin(plugin)
            metadata = plugin_adapter.get_metadata()
            Plugin.update(plugin, metadata)
        except errors.InvalidData:
            raise
        except Exception as e:
            logger.error("cannot update plugin {0} in DB. Reason: {1}"
                         .format(plugin.name, str(e)))

    @classmethod
    def _plugin_delete(cls, plugin):
        """Delete plugin

        :param plugin: A plugin instance
        :type plugin: plugin model
        """
        if cls._is_plugin_deletable(plugin):
            try:
                Plugin.delete(plugin)
            except Exception as e:
                logger.error("cannot delete plugin {0} from DB. Reason: {1}"
                             .format(plugin.name, str(e)))
        else:
            logger.error("cannot delete plugin {0} from DB. The one of "
                         "possible reasons: is still used at least in "
                         "one cluster, but it is already deleted on "
                         "filesystem. Please reinstall it using package "
                         "or disable it in every cluster".format(plugin.name))

    @classmethod
    def _plugin_create(cls, plugin_dir):
        """Create plugin using metadata.

        :param plugin_dir: a plugin directory name on FS
        :type plugin_dir: str
        """
        plugin_path = os.path.join(settings.PLUGINS_PATH, plugin_dir,
                                   'metadata.yaml')
        try:
            plugin_metadata = cls._parse_yaml_file(plugin_path)
            Plugin.create(plugin_metadata)
        except Exception as e:
            logger.error("cannot create plugin {0} from FS. Reason: {1}"
                         .format(plugin_dir, str(e)))

    @classmethod
    def _parse_yaml_file(cls, path):
        """Parses yaml

        :param str path: path to yaml file
        :returns: deserialized file
        """
        with io.open(path, encoding='utf-8') as f:
            data = yaml.load(f)

        return data

    @classmethod
    def _list_plugins_on_fs(cls):
        """Return list of plugins on FS

        :returns: list containing the names of the plugins in the directory
        """
        return os.listdir(settings.PLUGINS_PATH)

    @classmethod
    def enable_plugins_by_components(cls, cluster):
        """Enable plugin by components.

        :param cluster: A cluster instance
        :type cluster: Cluster model
        """
        cluster_components = set(cluster.components)
        plugin_ids = [p.id for p in PluginCollection.all_newest()]

        for plugin in ClusterPlugin.get_connected_plugins(
                cluster, plugin_ids):
            plugin_adapter = wrap_plugin(plugin)
            plugin_components = set(
                component['name']
                for component in plugin_adapter.components_metadata)

            if cluster_components & plugin_components:
                ClusterPlugin.set_attributes(
                    cluster.id, plugin.id, enabled=True)

    @classmethod
    def get_legacy_tasks_for_cluster(cls, cluster):
        """Gets the tasks from tasks.yaml for all plugins.

        :param cluster: the cluster object
        :return: all tasks from tasks.yaml
        """
        tasks = []
        for plugin in cls.get_enabled_plugins(cluster):
            tasks.extend(plugin.tasks)
        return tasks

    @classmethod
    def _is_plugin_deletable(cls, plugin):
        """Check if plugin deletion is enable

        :param plugin: the plugin instance
        :type plugin: plugin model
        :returns: boolean
        """
        return not ClusterPlugin.is_plugin_used(plugin.id)

    @classmethod
    def _get_specific_version(cls, versions, plugin_id):
        """Return plugin attributes for specific version.

        :returns: dict -- plugin attributes
        """
        for version in versions:
            if version['metadata']['plugin_id'] == plugin_id:
                return version

        return {}
