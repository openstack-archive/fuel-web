# -*- coding: utf-8 -*-

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


from distutils.version import LooseVersion
from itertools import groupby
import operator

import six

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.objects import DeploymentGraph
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.serializers.plugin import PluginSerializer
from nailgun import plugins


class Plugin(NailgunObject):

    model = models.Plugin
    serializer = PluginSerializer

    @classmethod
    def create(cls, data):

        graphs = data.pop("graphs", {})
        deployment_tasks = data.pop("deployment_tasks", [])
        releases_relations = [
            r for r in data.pop("releases", [])
            if not r.get('is_release', False)
        ]
        data['releases'] = releases_relations
        plugin_obj = super(Plugin, cls).create(data)

        if not graphs.get(consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE):
            graphs[consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE] = \
                {'tasks': deployment_tasks}

        for graph_type, graph_data in six.iteritems(graphs):
            DeploymentGraph.create_for_model(
                graph_data, plugin_obj, graph_type)

        plugin_adapter = plugins.wrap_plugin(plugin_obj)

        # todo(ikutukov): this update is a smell from the current plugins
        # installation schema. Remove it.

        cls.update(plugin_obj, plugin_adapter.get_metadata())

        ClusterPlugin.add_compatible_clusters(plugin_obj)

        return plugin_obj

    @classmethod
    def get_by_name_version(cls, name, version):
        return db()\
            .query(cls.model)\
            .filter_by(name=name, version=version)\
            .first()

    @classmethod
    def delete(cls, instance):
        """Delete plugin.

        :param instance: Plugin model instance
        :type instance: models.Plugin
        """
        DeploymentGraph.delete_for_parent(instance)
        super(Plugin, cls).delete(instance)


class PluginCollection(NailgunCollection):

    single = Plugin

    @classmethod
    def all_newest(cls):
        """Returns plugins in most recent versions

        Example:
        There are 4 plugins:
        - name: plugin_name, version: 1.0.0
        - name: plugin_name, version: 2.0.0
        - name: plugin_name, version: 0.1.0
        - name: plugin_another_name, version: 1.0.0
        In this case the method returns 2 plugins:
        - name: plugin_name, version: 2.0.0
        - name: plugin_another_name, version: 1.0.0

        :returns: list of Plugin models
        """
        newest_plugins = []

        get_name = operator.attrgetter('name')
        grouped_by_name = groupby(sorted(cls.all(), key=get_name), get_name)
        for name, plugins_group in grouped_by_name:
            newest_plugin = max(
                plugins_group,
                key=lambda p: LooseVersion(p.version)
            )

            newest_plugins.append(newest_plugin)

        return newest_plugins

    @classmethod
    def get_by_uids(cls, plugin_ids):
        """Returns plugins by given IDs.

        :param plugin_ids: list of plugin IDs
        :type plugin_ids: list
        :returns: iterable (SQLAlchemy query)
        """
        return cls.filter_by_id_list(cls.all(), plugin_ids)

    @classmethod
    def get_by_release(cls, release):
        """Returns plugins by given release

        :param release: Release instance
        :type release: Release DB model
        :returns: list -- list of sorted plugins
        """
        release_plugins = set()
        release_os = release.operating_system.lower()
        release_version = release.version

        for plugin in PluginCollection.all():
            for plugin_release in plugin.releases:
                if (release_os == plugin_release.get('os') and
                        release_version == plugin_release.get('version')):
                    release_plugins.add(plugin)

        return sorted(release_plugins, key=lambda plugin: plugin.name)


class ClusterPlugin(NailgunObject):

    model = models.ClusterPlugin

    @classmethod
    def is_compatible(cls, cluster, plugin):
        """Validates if plugin is compatible with cluster.

        :param cluster: A cluster instance
        :type cluster: nailgun.db.sqlalchemy.models.cluster.Cluster
        :param plugin: A plugin instance
        :type plugin: nailgun.db.sqlalchemy.models.plugins.Plugin
        :return: True if compatible, False if not
        :rtype: bool
        """
        plugin_adapter = plugins.wrap_plugin(plugin)

        return plugin_adapter.validate_compatibility(cluster)

    @classmethod
    def get_compatible_plugins(cls, cluster):
        """Returns a list of plugins that are compatible with a given cluster.

        :param cluster: A cluster instance
        :type cluster: nailgun.db.sqlalchemy.models.cluster.Cluster
        :return: A list of plugin instances
        :rtype: list
        """
        return list(six.moves.filter(
            lambda p: cls.is_compatible(cluster, p),
            PluginCollection.all()))

    @classmethod
    def add_compatible_plugins(cls, cluster):
        """Populates 'cluster_plugins' table with compatible plugins.

        :param cluster: A cluster instance
        :type cluster: nailgun.db.sqlalchemy.models.cluster.Cluster
        """
        for plugin in cls.get_compatible_plugins(cluster):
            plugin_attributes = dict(plugin.attributes_metadata)
            plugin_attributes.pop('metadata', None)
            cls.create({
                'cluster_id': cluster.id,
                'plugin_id': plugin.id,
                'enabled': False,
                'attributes': plugin_attributes
            })

    @classmethod
    def get_compatible_clusters(cls, plugin):
        """Returns a list of clusters that are compatible with a given plugin.

        :param plugin: A plugin instance
        :type plugin: nailgun.db.sqlalchemy.models.plugins.Plugin
        :return: A list of cluster instances
        :rtype: list
        """
        return list(six.moves.filter(
            lambda c: cls.is_compatible(c, plugin),
            db().query(models.Cluster)))

    @classmethod
    def add_compatible_clusters(cls, plugin):
        """Populates 'cluster_plugins' table with compatible cluster.

        :param plugin: A plugin instance
        :type plugin: nailgun.db.sqlalchemy.models.plugins.Plugin
        """
        plugin_attributes = dict(plugin.attributes_metadata)
        plugin_attributes.pop('metadata', None)
        for cluster in cls.get_compatible_clusters(plugin):
            cluster_plugin = cls.create({
                'cluster_id': cluster.id,
                'plugin_id': plugin.id,
                'enabled': False,
                'attributes': plugin_attributes
            })

            # Set default attributes for Nodes, NICs and Bonds during
            # plugin installation
            NodeNICInterfaceClusterPlugin.add_node_nics_for_cluster_plugin(
                cluster_plugin)
            NodeBondInterfaceClusterPlugin.add_node_bonds_for_cluster_plugin(
                cluster_plugin)

        db().flush()

    @classmethod
    def set_attributes(cls, cluster_id, plugin_id, enabled=None, attrs=None):
        """Sets plugin's attributes in cluster_plugins table.

        :param cluster_id: Cluster ID
        :type cluster_id: int
        :param plugin_id: Plugin ID
        :type plugin_id: int
        :param enabled: Enabled or disabled plugin for given cluster
        :type enabled: bool
        :param attrs: Plugin metadata
        :type attrs: dict
        """
        params = {}
        if enabled is not None:
            params['enabled'] = enabled
        if attrs is not None:
            params['attributes'] = attrs

        db().query(cls.model)\
            .filter_by(plugin_id=plugin_id, cluster_id=cluster_id)\
            .update(params, synchronize_session='fetch')
        db().flush()

    @classmethod
    def get_connected_plugins_data(cls, cluster_id):
        """Returns plugins and cluster_plugins data connected with cluster.

        :param cluster_id: Cluster ID
        :type cluster_id: int
        :returns: List of mixed data from plugins and cluster_plugins
        :rtype: iterable (SQLAlchemy query)
        """
        return db().query(
            models.Plugin.id,
            models.Plugin.name,
            models.Plugin.title,
            models.Plugin.version,
            models.Plugin.is_hotpluggable,
            models.Plugin.attributes_metadata,
            cls.model.enabled,
            cls.model.attributes
        ).join(cls.model)\
            .filter(cls.model.cluster_id == cluster_id)\
            .order_by(models.Plugin.name, models.Plugin.version)

    @classmethod
    def get_connected_plugins(cls, cluster, plugin_ids=None):
        """Returns plugins connected with given cluster.

        :param cluster: Cluster instance
        :type cluster: Cluster SQLAlchemy model
        :param plugin_ids: List of specific plugins ids to chose from
        :type plugin_ids: list
        :returns: List of plugins
        :rtype: iterable (SQLAlchemy query)
        """
        plugins = db().query(
            models.Plugin
        ).join(cls.model)\
            .filter(cls.model.cluster_id == cluster.id)\
            .order_by(models.Plugin.name, models.Plugin.version)

        if plugin_ids:
            plugins = plugins.filter(cls.model.plugin_id.in_(plugin_ids))

        return plugins

    @classmethod
    def get_connected_clusters(cls, plugin_id):
        """Returns clusters connected with given plugin.

        :param plugin_id: Plugin ID
        :type plugin_id: int
        :returns: List of clusters
        :rtype: iterable (SQLAlchemy query)
        """
        return db()\
            .query(models.Cluster)\
            .join(cls.model)\
            .filter(cls.model.plugin_id == plugin_id)\
            .order_by(models.Cluster.name)

    @classmethod
    def get_enabled(cls, cluster_id):
        """Returns a list of plugins enabled for a given cluster.

        :param cluster_id: Cluster ID
        :type cluster_id: int
        :returns: List of plugin instances
        :rtype: iterable (SQLAlchemy query)
        """
        return db().query(models.Plugin)\
            .join(cls.model)\
            .filter(cls.model.cluster_id == cluster_id)\
            .filter(cls.model.enabled.is_(True))\
            .order_by(models.Plugin.id)

    @classmethod
    def is_plugin_used(cls, plugin_id):
        """Check if plugin is used for any cluster or not.

        :param plugin_id: Plugin ID
        :type plugin_id: int
        :return: True if some cluster uses this plugin
        :rtype: bool
        """
        q = db().query(cls.model)\
            .filter(cls.model.plugin_id == plugin_id)\
            .filter(cls.model.enabled.is_(True))

        return db().query(q.exists()).scalar()


class BasicNodeClusterPlugin(NailgunObject):

    @classmethod
    def set_attributes(cls, instance_id, attrs=None):
        """Update plugin NIC|Bond|Node attributes

        :param instance_id: NIC|Bond|Node instance id
        :type instance: int
        :returns: None
        """
        if attrs:
            db().query(cls.model)\
                .filter_by(
                    id=instance_id)\
                .update({'attributes': attrs}, synchronize_session='fetch')

            db().flush()


class NodeNICInterfaceClusterPlugin(BasicNodeClusterPlugin):

    model = models.NodeNICInterfaceClusterPlugin

    @classmethod
    def get_all_enabled_attributes_by_interface(cls, interface):
        """Returns plugin enabled attributes for specific NIC.

        :param interface: Interface instance
        :type interface: models.node.NodeNICInterface
        :returns: dict -- Dict object with plugin NIC attributes
        """
        nic_attributes = {}
        nic_plugin_attributes_query = db().query(
            cls.model.id,
            models.Plugin.name,
            models.Plugin.title,
            cls.model.attributes
        ).join(
            models.ClusterPlugin,
        ).filter(
            cls.model.interface_id == interface.id
        ).filter(
            models.ClusterPlugin.enabled.is_(True)).all()

        for nic_plugin_id, name, title, attributes \
                in nic_plugin_attributes_query:
            nic_attributes[name] = {
                'metadata': {
                    'label': title,
                    'nic_plugin_id': nic_plugin_id,
                    'class': 'plugin'
                }
            }
            # TODO(apopovych): resolve conflicts of same attribute names
            # for different plugins
            nic_attributes[name].update(attributes)

        return nic_attributes

    @classmethod
    def add_node_nics_for_cluster_plugin(cls, cluster_plugin):
        """Populates 'node_nic_interface_cluster_plugins' table.

        :param cluster_plugin: ClusterPlugin instance
        :type cluster_plugin: models.cluster.ClusterPlugin
        :returns: None
        """
        nic_attributes = dict(
            cluster_plugin.plugin.nic_attributes_metadata)
        for node in cluster_plugin.cluster.nodes:
            for interface in node.nic_interfaces:
                if nic_attributes:
                    cls.create({
                        'cluster_plugin_id': cluster_plugin.id,
                        'interface_id': interface.id,
                        'node_id': node.id,
                        'attributes': nic_attributes
                    })

        db().flush()

    @classmethod
    def add_cluster_plugins_for_node_nic(cls, interface):
        """Populates 'node_nic_interface_cluster_plugins' table.

        :param interface: Interface instance
        :type interface: models.node.NodeNICInterface
        :returns: None
        """
        node = interface.node
        # remove old relations for interfaces
        nic_cluster_plugin_ids = set(
            item.id for item in node.node_nic_interface_cluster_plugins
            if item.interface_id == interface.id)
        cls.bulk_delete(nic_cluster_plugin_ids)

        for cluster_plugin in node.cluster.cluster_plugins:
            nic_attributes = dict(
                cluster_plugin.plugin.nic_attributes_metadata)
            if nic_attributes:
                cls.create({
                    'cluster_plugin_id': cluster_plugin.id,
                    'interface_id': interface.id,
                    'node_id': node.id,
                    'attributes': nic_attributes
                })

        db().flush()


class NodeBondInterfaceClusterPlugin(BasicNodeClusterPlugin):

    model = models.NodeBondInterfaceClusterPlugin

    @classmethod
    def get_all_enabled_attributes_by_bond(cls, bond):
        """Returns plugin enabled attributes for specific Bond.

        :param interface: Bond instance
        :type interface: models.node.NodeBondInterface
        :returns: dict -- Dict object with plugin Bond attributes
        """
        bond_attributes = {}
        bond_plugin_attributes_query = db().query(
            cls.model.id,
            models.Plugin.name,
            models.Plugin.title,
            cls.model.attributes
        ).join(
            models.ClusterPlugin,
            models.Plugin
        ).filter(
            cls.model.bond_id == bond.id
        ).filter(
            models.ClusterPlugin.enabled.is_(True))

        for bond_plugin_id, name, title, attributes \
                in bond_plugin_attributes_query:
            bond_attributes[name] = {
                'metadata': {
                    'label': title,
                    'bond_plugin_id': bond_plugin_id,
                    'class': 'plugin'
                }
            }
            # TODO(apopovych): resolve conflicts of same attribute names
            # for different plugins
            bond_attributes[name].update(attributes)

        return bond_attributes

    @classmethod
    def add_node_bonds_for_cluster_plugin(cls, cluster_plugin):
        """Populates 'node_bond_interface_cluster_plugins' table with bonds.

        :param cluster_plugin: ClusterPlugin instance
        :type cluster_plugin: models.cluster.ClusterPlugin
        :returns: None
        """
        bond_attributes = dict(
            cluster_plugin.plugin.bond_attributes_metadata)
        for node in cluster_plugin.cluster.nodes:
            for bond in node.bond_interfaces:
                if bond_attributes:
                    cls.create({
                        'cluster_plugin_id': cluster_plugin.id,
                        'bond_id': bond.id,
                        'node_id': node.id,
                        'attributes': bond_attributes
                    })

        db().flush()

    @classmethod
    def add_cluster_plugins_for_node_bond(cls, bond):
        """Populates 'node_bond_interface_cluster_plugins' table.

        :param interface: Bond instance
        :type interface: models.node.NodeBondInterface
        :returns: None
        """
        node = bond.node
        # remove old relations for bonds
        bond_cluster_plugin_ids = set(
            item.id for item in node.node_bond_interface_cluster_plugins
            if item.bond_id == bond.id)
        cls.bulk_delete(bond_cluster_plugin_ids)

        for cluster_plugin in node.cluster.cluster_plugins:
            bond_attributes = dict(
                cluster_plugin.plugin.bond_attributes_metadata)
            if bond_attributes:
                cls.create({
                    'cluster_plugin_id': cluster_plugin.id,
                    'bond_id': bond.id,
                    'node_id': node.id,
                    'attributes': bond_attributes
                })

        db().flush()
