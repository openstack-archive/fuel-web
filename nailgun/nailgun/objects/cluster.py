# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

"""
Cluster-related objects and collections
"""

import copy
from distutils.version import StrictVersion
import itertools


import six
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql
from sqlalchemy.orm.exc import MultipleResultsFound
from sqlalchemy.orm.exc import NoResultFound

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.errors import errors
from nailgun.extensions import fire_callback_on_cluster_delete
from nailgun.extensions import fire_callback_on_node_collection_delete
from nailgun.logger import logger
from nailgun.objects import DeploymentGraph
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.plugin import ClusterPlugins
from nailgun.objects import Release
from nailgun.objects.serializers.cluster import ClusterSerializer
from nailgun.plugins.manager import PluginManager
from nailgun.policy.merge import NetworkRoleMergePolicy
from nailgun.settings import settings
from nailgun.utils import AttributesGenerator
from nailgun.utils import dict_merge
from nailgun.utils import traverse


class Attributes(NailgunObject):
    """Cluster attributes object."""

    #: SQLAlchemy model for Cluster attributes
    model = models.Attributes

    @classmethod
    def generate_fields(cls, instance):
        """Generate field values for Cluster attributes using generators.

        :param instance: Attributes instance
        :returns: None
        """
        instance.generated = traverse(
            instance.generated or {},
            AttributesGenerator,
            {
                'cluster': instance.cluster,
                'settings': settings,
            }
        )

        # TODO(ikalnitsky):
        #
        # Think about traversing "editable" attributes. It might be very
        # useful to generate default values for editable attribute at
        # cluster creation time.

    @classmethod
    def merged_attrs(cls, instance):
        """Generates merged dict of attributes

        Result includes generated Cluster attributes recursively updated
        by new values from editable attributes

        :param instance: Attributes instance
        :returns: dict of merged attributes
        """
        return dict_merge(
            instance.generated,
            instance.editable
        )

    @classmethod
    def merged_attrs_values(cls, instance):
        """Transforms raw dict of attributes into dict of facts

        Raw dict is taken from :func:`merged_attrs`
        The result of this function is a dict of facts that wil be sent to
        orchestrator

        :param instance: Attributes instance
        :returns: dict of merged attributes
        """
        attrs = cls.merged_attrs(instance)
        for group_attrs in attrs.itervalues():
            for attr, value in group_attrs.iteritems():
                if isinstance(value, dict) and 'value' in value:
                    group_attrs[attr] = value['value']
        if 'common' in attrs:
            attrs.update(attrs.pop('common'))
        if 'additional_components' in attrs:
            for comp, enabled in attrs['additional_components'].iteritems():
                if isinstance(enabled, bool):
                    attrs.setdefault(comp, {}).update({
                        "enabled": enabled
                    })

            attrs.pop('additional_components')
        return attrs


class Cluster(NailgunObject):
    """Cluster object."""

    #: SQLAlchemy model for Cluster
    model = models.Cluster

    #: Serializer for Cluster
    serializer = ClusterSerializer

    @classmethod
    def create(cls, data):
        """Create Cluster instance with specified parameters in DB.

        This includes:
        * creating Cluster attributes and generating default values \
        (see :func:`create_attributes`)
        * creating NetworkGroups for Cluster
        * adding default pending changes (see :func:`add_pending_changes`)
        * if "nodes" are specified in data then they are added to Cluster \
        (see :func:`update_nodes`)

        :param data: dictionary of key-value pairs as object fields
        :returns: Cluster instance
        """

        # TODO(enchantner): fix this temporary hack in clients
        if "release_id" not in data:
            release_id = data.pop("release", None)
            data["release_id"] = release_id

        # remove read-only attribute
        data.pop("is_locked", None)
        assign_nodes = data.pop("nodes", [])
        enabled_editable_attributes = None

        if 'components' in data:
            enabled_core_attributes = cls.get_cluster_attributes_by_components(
                data['components'], data["release_id"])
            data = dict_merge(data, enabled_core_attributes['cluster'])
            enabled_editable_attributes = enabled_core_attributes['editable']

        data["fuel_version"] = settings.VERSION["release"]
        deployment_tasks = data.pop("deployment_tasks", None)

        cluster = super(Cluster, cls).create(data)
        cls.create_default_group(cluster)

        cls.create_attributes(cluster, enabled_editable_attributes)
        cls.create_vmware_attributes(cluster)
        cls.create_default_extensions(cluster)

        if deployment_tasks:
            deployment_graph = DeploymentGraph.create(deployment_tasks)
            DeploymentGraph.attach_to_model(deployment_graph, cluster)

        try:
            net_manager = cls.get_network_manager(cluster)
            net_manager.create_network_groups_and_config(cluster, data)

            cls.add_pending_changes(
                cluster, consts.CLUSTER_CHANGES.attributes)
            cls.add_pending_changes(
                cluster, consts.CLUSTER_CHANGES.networks)
            cls.add_pending_changes(
                cluster, consts.CLUSTER_CHANGES.vmware_attributes)

            if assign_nodes:
                cls.update_nodes(cluster, assign_nodes)

            ClusterPlugins.add_compatible_plugins(cluster)
            PluginManager.enable_plugins_by_components(cluster)

            net_manager.assign_vips_for_net_groups(cluster)

        except (
            errors.OutOfVLANs,
            errors.OutOfIPs,
            errors.NoSuitableCIDR,

            # VIP assignment related errors
            errors.CanNotFindCommonNodeGroup,
            errors.CanNotFindNetworkForNodeGroup,
            errors.DuplicatedVIPNames
        ) as exc:
            raise errors.CannotCreate(exc.message)

        return cluster

    @classmethod
    def get_cluster_attributes_by_components(cls, components, release_id):
        """Enable cluster attributes by given components

        :param components: list of component names
        :type components: list of strings
        :param release_id: Release model id
        :type release_id: str
        :returns: dict -- objects with enabled attributes for cluster
        """

        def _update_attributes_dict_by_binds_exp(bind_exp, value):
            """Update cluster and attributes data with bound values

            :param bind_exp: path to specific attribute for model in format
                             model:some.attribute.value. Model can be
                             settings|cluster
            :type bind_exp: str
            :param value: value for specific attribute
            :type value: bool|str|int
            :returns: None
            """
            model, attr_expr = bind_exp.split(':')
            if model not in ('settings', 'cluster'):
                return

            path_items = attr_expr.split('.')
            path_items.insert(0, model)
            attributes = cluster_attributes
            for i in six.moves.range(0, len(path_items) - 1):
                attributes = attributes.setdefault(path_items[i], {})
            attributes[path_items[-1]] = value

        release = Release.get_by_uid(release_id)
        cluster_attributes = {}
        for component in Release.get_all_components(release):
            if component['name'] in components:
                for bind_item in component.get('bind', []):
                    if isinstance(bind_item, six.string_types):
                        _update_attributes_dict_by_binds_exp(bind_item, True)
                    elif isinstance(bind_item, list):
                        _update_attributes_dict_by_binds_exp(bind_item[0],
                                                             bind_item[1])
        return {
            'editable': cluster_attributes.get('settings', {}),
            'cluster': cluster_attributes.get('cluster', {})
        }

    @classmethod
    def delete(cls, instance):
        node_ids = [
            _id for (_id,) in
            db().query(models.Node.id).
            filter_by(cluster_id=instance.id).
            order_by(models.Node.id)]
        fire_callback_on_node_collection_delete(node_ids)
        fire_callback_on_cluster_delete(instance)
        super(Cluster, cls).delete(instance)

    @classmethod
    def get_default_kernel_params(cls, instance):
        kernel_params = instance.attributes.editable.get("kernel_params", {})
        return kernel_params.get("kernel", {}).get("value")

    @classmethod
    def create_attributes(cls, instance, editable_attributes=None):
        """Create attributes for Cluster instance, generate their values

        (see :func:`Attributes.generate_fields`)

        :param instance: Cluster instance
        :param editable_attributes: key-value dictionary represents editable
            attributes that will be merged with default editable attributes
        :returns: None
        """
        merged_editable_attributes = \
            cls.get_default_editable_attributes(instance)
        if editable_attributes:
            merged_editable_attributes = dict_merge(
                merged_editable_attributes, editable_attributes)
        attributes = Attributes.create(
            {
                "editable": merged_editable_attributes,
                "generated": instance.release.attributes_metadata.get(
                    "generated"
                ),
                "cluster_id": instance.id
            }
        )
        Attributes.generate_fields(attributes)
        db().flush()
        return attributes

    @classmethod
    def create_default_extensions(cls, instance):
        """Sets default extensions list from release model

        :param instance: Cluster instance
        :returns: None
        """
        instance.extensions = instance.release.extensions
        db().flush()

    @classmethod
    def get_default_editable_attributes(cls, instance):
        """Get editable attributes from release metadata

        :param instance: Cluster instance
        :returns: Dict object
        """
        editable = instance.release.attributes_metadata.get("editable")
        # Add default attributes of connected plugins
        plugin_attrs = PluginManager.get_plugins_attributes(
            instance, all_versions=True, default=True)
        editable = dict(plugin_attrs, **editable)
        editable = traverse(editable, AttributesGenerator, {
            'cluster': instance,
            'settings': settings,
        })

        return editable

    @classmethod
    def get_attributes(cls, instance, all_plugins_versions=False):
        """Get attributes for current Cluster instance.

        :param instance: Cluster instance
        :param all_plugins_versions: Get attributes of all versions of plugins
        :returns: dict
        """
        try:
            attrs = db().query(models.Attributes).filter(
                models.Attributes.cluster_id == instance.id
            ).one()
        except MultipleResultsFound:
            raise errors.InvalidData(
                u"Multiple rows with attributes were found for cluster '{0}'"
                .format(instance.name)
            )
        except NoResultFound:
            raise errors.InvalidData(
                u"No attributes were found for cluster '{0}'"
                .format(instance.name)
            )
        attrs = copy.deepcopy(attrs)

        # Merge plugins attributes into editable ones
        plugin_attrs = PluginManager.get_plugins_attributes(
            instance, all_versions=all_plugins_versions)
        plugin_attrs = traverse(plugin_attrs, AttributesGenerator, {
            'cluster': instance,
            'settings': settings,
        })
        attrs['editable'].update(plugin_attrs)

        return attrs

    @classmethod
    def get_editable_attributes(cls, instance, all_plugins_versions=False):
        """Get editable attributes for current Cluster instance.

        :param instance: Cluster instance
        :param all_plugins_versions: Get attributes of all versions of plugins
        :return: dict
        """
        return cls.get_attributes(instance, all_plugins_versions)['editable']

    @classmethod
    def update_attributes(cls, instance, data):
        PluginManager.process_cluster_attributes(instance, data['editable'])
        for key, value in data.iteritems():
            setattr(instance.attributes, key, value)
        cls.add_pending_changes(instance, "attributes")
        db().flush()

    @classmethod
    def patch_attributes(cls, instance, data):
        PluginManager.process_cluster_attributes(instance, data['editable'])
        instance.attributes.editable = dict_merge(
            instance.attributes.editable, data['editable'])
        cls.add_pending_changes(instance, "attributes")
        cls.get_network_manager(instance).update_restricted_networks(instance)
        db().flush()

    @classmethod
    def get_updated_editable_attributes(cls, instance, data):
        """Same as get_editable_attributes but also merges given data.

        :param instance: Cluster object
        :param data: dict
        :returns: dict
        """
        return {'editable': dict_merge(
            cls.get_editable_attributes(instance),
            data.get('editable', {})
        )}

    @classmethod
    def get_network_manager(cls, instance=None):
        """Get network manager for Cluster instance.

        If instance is None then the default NetworkManager is returned

        :param instance: Cluster instance
        :returns: NetworkManager/NovaNetworkManager/NeutronManager
        """
        if not instance:
            from nailgun.network.manager import NetworkManager
            return NetworkManager

        ver = instance.release.environment_version
        net_provider = instance.net_provider
        if net_provider == consts.CLUSTER_NET_PROVIDERS.neutron:
            from nailgun.network import neutron
            if StrictVersion(ver) < StrictVersion('6.1'):
                return neutron.NeutronManagerLegacy

            if StrictVersion(ver) == StrictVersion('6.1'):
                return neutron.NeutronManager61

            if StrictVersion(ver) == StrictVersion('7.0'):
                return neutron.NeutronManager70

            if StrictVersion(ver) >= StrictVersion('8.0'):
                return neutron.NeutronManager80

            return neutron.NeutronManager
        elif net_provider == consts.CLUSTER_NET_PROVIDERS.nova_network:
            from nailgun.network import nova_network
            if StrictVersion(ver) < StrictVersion('6.1'):
                return nova_network.NovaNetworkManagerLegacy

            if StrictVersion(ver) == StrictVersion('6.1'):
                return nova_network.NovaNetworkManager61

            if StrictVersion(ver) == StrictVersion('7.0'):
                return nova_network.NovaNetworkManager70

            if StrictVersion(ver) >= StrictVersion('8.0'):
                raise errors.NovaNetworkNotSupported()

            return nova_network.NovaNetworkManager

        raise ValueError(
            'The network provider "{0}" is not supported.'
            .format(net_provider)
        )

    @classmethod
    def add_pending_changes(cls, instance, changes_type, node_id=None):
        """Add pending changes for current Cluster.

        If node_id is specified then links created changes with node.

        :param instance: Cluster instance
        :param changes_type: name of changes to add
        :param node_id: node id for changes
        :returns: None
        """
        logger.debug(
            u"New pending changes in environment {0}: {1}{2}".format(
                instance.id,
                changes_type,
                u" node_id={0}".format(node_id) if node_id else u""
            )
        )

        # TODO(enchantner): check if node belongs to cluster
        ex_chs = db().query(models.ClusterChanges).filter_by(
            cluster=instance,
            name=changes_type
        )
        if not node_id:
            ex_chs = ex_chs.first()
        else:
            ex_chs = ex_chs.filter_by(node_id=node_id).first()
        # do nothing if changes with the same name already pending
        if ex_chs:
            return
        ch = models.ClusterChanges(
            cluster_id=instance.id,
            name=changes_type
        )
        if node_id:
            ch.node_id = node_id

        db().add(ch)
        db().flush()

    @classmethod
    def get_nodes_not_for_deletion(cls, cluster):
        """All clusters nodes except nodes for deletion."""
        return db().query(models.Node).filter_by(
            cluster=cluster, pending_deletion=False).order_by(models.Node.id)

    @classmethod
    def clear_pending_changes(cls, instance, node_id=None):
        """Clear pending changes for current Cluster.

        If node_id is specified then only clears changes connected
        to this node.

        :param instance: Cluster instance
        :param node_id: node id for changes
        :returns: None
        """
        logger.debug(
            u"Removing pending changes in environment {0}{1}".format(
                instance.id,
                u" where node_id={0}".format(node_id) if node_id else u""
            )
        )
        chs = db().query(models.ClusterChanges).filter_by(
            cluster_id=instance.id
        )
        if node_id:
            chs = chs.filter_by(node_id=node_id)
        map(db().delete, chs.all())
        db().flush()

    @classmethod
    def update(cls, instance, data):
        """Update Cluster object instance with specified parameters in DB

        If "nodes" are specified in data then they will replace existing ones
        (see :func:`update_nodes`)

        :param instance: Cluster instance
        :param data: dictionary of key-value pairs as object fields
        :returns: Cluster instance
        """
        # remove read-only attributes
        data.pop("fuel_version", None)
        data.pop("is_locked", None)

        nodes = data.pop("nodes", None)
        changes = data.pop("changes", None)
        deployment_tasks = data.pop("deployment_tasks", None)

        super(Cluster, cls).update(instance, data)

        if deployment_tasks:
            deployment_graph = DeploymentGraph.create(deployment_tasks)
            DeploymentGraph.attach_to_model(deployment_graph, instance)

        if nodes is not None:
            cls.update_nodes(instance, nodes)
        if changes is not None:
            cls.update_changes(instance, changes)
        return instance

    @classmethod
    def update_nodes(cls, instance, nodes_ids):
        """Update Cluster nodes by specified node IDs

        Nodes with specified IDs will replace existing ones in Cluster

        :param instance: Cluster instance
        :param nodes_ids: list of nodes ids
        :returns: None
        """

        # TODO(NAME): sepatate nodes
        # for deletion and addition by set().
        new_nodes = []
        if nodes_ids:
            new_nodes = db().query(models.Node).filter(
                models.Node.id.in_(nodes_ids)
            )

        nodes_to_remove = [n for n in instance.nodes
                           if n not in new_nodes]
        nodes_to_add = [n for n in new_nodes
                        if n not in instance.nodes]

        for node in nodes_to_add:
            if not node.online:
                raise errors.NodeOffline(
                    u"Cannot add offline node "
                    u"'{0}' to environment".format(node.id)
                )

        # we should reset hostname to default value to guarantee
        # hostnames uniqueness for nodes outside clusters
        from nailgun.objects import Node
        for node in nodes_to_remove:
            node.hostname = Node.default_slave_name(node)

        map(instance.nodes.remove, nodes_to_remove)
        map(instance.nodes.append, nodes_to_add)

        net_manager = cls.get_network_manager(instance)
        map(
            net_manager.clear_assigned_networks,
            nodes_to_remove
        )
        map(
            net_manager.clear_bond_configuration,
            nodes_to_remove
        )
        cls.replace_provisioning_info_on_nodes(instance, [], nodes_to_remove)
        cls.replace_deployment_info_on_nodes(instance, [], nodes_to_remove)
        from nailgun.objects import NodeCollection
        NodeCollection.reset_network_template(nodes_to_remove)
        NodeCollection.reset_attributes(nodes_to_remove)

        from nailgun.objects import OpenstackConfig
        OpenstackConfig.disable_by_nodes(nodes_to_remove)

        map(
            net_manager.assign_networks_by_default,
            nodes_to_add
        )
        map(Node.set_default_attributes, nodes_to_add)
        cls.update_nodes_network_template(instance, nodes_to_add)
        db().flush()

    @classmethod
    def update_changes(cls, instance, changes):
        instance.changes_list = [
            models.ClusterChanges(**change) for change in changes
        ]
        db().flush()

    @classmethod
    def get_ifaces_for_network_in_cluster(cls, instance, net):
        """Method for receiving node_id:iface pairs for all nodes in cluster

        :param instance: Cluster instance
        :param net: Nailgun specific network name
        :type net: str
        :returns: List of node_id, iface pairs for all nodes in cluster.
        """
        nics_db = db().query(
            models.NodeNICInterface.node_id,
            models.NodeNICInterface.name
        ).filter(
            models.NodeNICInterface.node.has(cluster_id=instance.id),
            models.NodeNICInterface.assigned_networks_list.any(name=net)
        )
        bonds_db = db().query(
            models.NodeBondInterface.node_id,
            models.NodeBondInterface.name
        ).filter(
            models.NodeBondInterface.node.has(cluster_id=instance.id),
            models.NodeBondInterface.assigned_networks_list.any(name=net)
        )
        return nics_db.union(bonds_db)

    @classmethod
    def replace_provisioning_info_on_nodes(cls, instance, data, nodes):
        for node in nodes:
            node_data = next((n for n in data if node.uid == n.get('uid')), {})
            node.replaced_provisioning_info = node_data

    @classmethod
    def replace_deployment_info_on_nodes(cls, instance, data, nodes):
        for node in instance.nodes:
            node_data = [n for n in data if node.uid == n.get('uid')]
            node.replaced_deployment_info = node_data

    @classmethod
    def replace_provisioning_info(cls, instance, data):
        received_nodes = data.pop('nodes', [])
        instance.is_customized = True
        instance.replaced_provisioning_info = data
        cls.replace_provisioning_info_on_nodes(
            instance, received_nodes, instance.nodes)
        return cls.get_provisioning_info(instance)

    @classmethod
    def replace_deployment_info(cls, instance, data):
        instance.is_customized = True
        cls.replace_deployment_info_on_nodes(instance, data, instance.nodes)
        return cls.get_deployment_info(instance)

    @classmethod
    def get_provisioning_info(cls, instance):
        data = {}
        if instance.replaced_provisioning_info:
            data.update(instance.replaced_provisioning_info)
        nodes = []
        for node in instance.nodes:
            if node.replaced_provisioning_info:
                nodes.append(node.replaced_provisioning_info)
        if data:
            data['nodes'] = nodes
        return data

    @classmethod
    def get_deployment_info(cls, instance):
        data = []
        for node in instance.nodes:
            if node.replaced_deployment_info:
                data.extend(node.replaced_deployment_info)
        return data

    @classmethod
    def get_creds(cls, instance):
        return instance.attributes.editable['access']

    @classmethod
    def should_assign_public_to_all_nodes(cls, instance):
        """Check if Public network is to be assigned to all nodes in cluster

        :param instance: cluster instance
        :returns: True when Public network is to be assigned to all nodes
        """
        if instance.net_provider == \
                consts.CLUSTER_NET_PROVIDERS.nova_network:
            return True
        assignment = instance.attributes.editable.get(
            'public_network_assignment')
        if not assignment or assignment['assign_to_all_nodes']['value']:
            return True
        return False

    @classmethod
    def neutron_dvr_enabled(cls, instance):
        neutron_attrs = instance.attributes.editable.get(
            'neutron_advanced_configuration')
        if neutron_attrs:
            return neutron_attrs['neutron_dvr']['value']
        else:
            return False

    @classmethod
    def get_roles(cls, instance):
        """Returns a dictionary of node roles available for deployment.

        :param instance: cluster instance
        :returns: a dictionary of roles metadata
        """
        available_roles = copy.deepcopy(instance.release.roles_metadata)
        available_roles.update(
            PluginManager.get_plugins_node_roles(instance))
        return available_roles

    @classmethod
    def set_primary_role(cls, instance, nodes, role_name):
        """Method for assigning primary attribute for specific role.

        - verify that there is no primary attribute of specific role
          assigned to cluster nodes with this role in role list
          or pending role list, and this node is not marked for deletion
        - if there is no primary role assigned, filter nodes which have current
          role in roles or pending_roles
        - if there is nodes with ready state - they should have higher priority
        - if role was in primary_role_list - change primary attribute
          for that association, same for role_list, this is required
          because deployment_serializer used by cli to generate deployment info

        :param instance: Cluster db objects
        :param nodes: list of Node db objects
        :param role_name: string with known role name
        """
        if role_name not in cls.get_roles(instance):
            logger.warning(
                'Trying to assign primary for non-existing role %s', role_name)
            return

        node = cls.get_primary_node(instance, role_name)
        if not node:
            # get nodes with a given role name which are not going to be
            # removed
            filtered_nodes = []
            for node in nodes:
                if (not node.pending_deletion and (
                        role_name in set(node.roles + node.pending_roles))):
                    filtered_nodes.append(node)
            filtered_nodes = sorted(filtered_nodes, key=lambda node: node.id)

            if filtered_nodes:
                primary_node = next((
                    node for node in filtered_nodes
                    if node.status == consts.NODE_STATUSES.ready),
                    filtered_nodes[0])

                primary_node.primary_roles = list(primary_node.primary_roles)
                primary_node.primary_roles.append(role_name)

        db().flush()

    @classmethod
    def set_primary_roles(cls, instance, nodes):
        """Assignment of all primary attribute for all roles that requires it.

        This method is idempotent
        To mark role as primary add has_primary: true attribute to release

        :param instance: Cluster db object
        :param nodes: list of Node db objects
        """
        if not instance.is_ha_mode:
            return
        roles_metadata = cls.get_roles(instance)
        for role, meta in six.iteritems(roles_metadata):
            if meta.get('has_primary'):
                cls.set_primary_role(instance, nodes, role)

    @classmethod
    def get_nodes_by_role(cls, instance, role_name):
        """Get nodes related to some specific role

        :param instance: cluster db object
        :type: python object
        :param role_name: node role name
        :type: string
        """

        if role_name not in cls.get_roles(instance):
            logger.warning("%s role doesn't exist", role_name)
            return []

        nodes = db().query(models.Node).filter_by(
            cluster_id=instance.id
        ).filter(sa.or_(
            models.Node.roles.any(role_name),
            models.Node.pending_roles.any(role_name)
        )).all()

        return nodes

    @classmethod
    def get_nodes_by_status(cls, instance, status, exclude=None):
        """Get cluster nodes with particular status

        :param instance: cluster instance
        :param status: node status
        :param exclude: the list of uids to exclude
        :return: filtered query on nodes
        """
        query = db().query(models.Node).filter_by(
            cluster_id=instance.id,
            status=status
        )
        if exclude:
            query = query.filter(sa.not_(models.Node.id.in_(exclude)))
        return query

    @classmethod
    def get_primary_node(cls, instance, role_name):
        """Get primary node for role_name

        If primary node is not found None will be returned
        Pending roles and roles are used in search

        :param instance: cluster db object
        :type: python object
        :param role_name: node role name
        :type: string
        :returns: node db object or None
        """
        logger.debug("Getting primary node for role: %s", role_name)

        if role_name not in cls.get_roles(instance):
            logger.debug("Role not found: %s", role_name)
            return None

        primary_node = db().query(models.Node).filter_by(
            pending_deletion=False,
            cluster_id=instance.id
        ).filter(
            models.Node.primary_roles.any(role_name)
        ).first()

        if primary_node is None:
            logger.debug("Not found primary node for role: %s", role_name)
        else:
            logger.debug("Found primary node: %s for role: %s",
                         primary_node.id, role_name)
        return primary_node

    @classmethod
    def get_controllers_group_id(cls, instance):
        return cls.get_controllers_node_group(instance).id

    @classmethod
    def get_controllers_node_group(cls, instance):
        return cls.get_common_node_group(instance, ['controller'])

    @classmethod
    def get_common_node_group(cls, instance, noderoles):
        """Returns a common node group for a given node roles.

        If a given node roles have different node groups, the error
        will be raised, so it's mandatory to have them the same
        node group.

        :param instance: a Cluster instance
        :param noderoles: a list of node roles
        :returns: a common NodeGroup instance
        """

        nodegroups = cls.get_node_groups(instance, noderoles).all()

        # NOTE(ikalnitsky):
        #   The 'nodegroups' may be an empty list only in case when there's
        #   no nodes with a given 'noderoles' in the cluster. I think we
        #   should reconsider this behaviour, and propogate some error up
        #   above, because returning default node group doesn't look like
        #   a right choice here.
        if not nodegroups:
            return cls.get_default_group(instance)

        if len(nodegroups) > 1:
            raise errors.CanNotFindCommonNodeGroup(
                'Node roles [{0}] has more than one common node group'.format(
                    ', '.join(noderoles)))

        return nodegroups[0]

    @classmethod
    def get_node_groups(cls, instance, noderoles):
        """Returns node groups for given node roles.

        :param instance: a Cluster instance
        :param noderoles: a list of node roles
        :returns: a query for list of NodeGroup instances
        """
        psql_noderoles = sa.cast(
            psql.array(noderoles),
            psql.ARRAY(sa.String(consts.ROLE_NAME_MAX_SIZE)))

        nodegroups = db().query(models.NodeGroup).join(models.Node).filter(
            models.Node.cluster_id == instance.id,
            models.Node.pending_deletion.is_(False)
        ).filter(sa.or_(
            models.Node.roles.overlap(psql_noderoles),
            models.Node.pending_roles.overlap(psql_noderoles)
        ))

        return nodegroups

    @classmethod
    def get_bond_interfaces_for_all_nodes(cls, instance, networks=None):
        bond_interfaces_query = db().query(models.NodeBondInterface).\
            join(models.Node).filter(models.Node.cluster_id == instance.id)
        if networks:
            bond_interfaces_query = bond_interfaces_query.join(
                models.NodeBondInterface.assigned_networks_list,
                aliased=True).filter(models.NetworkGroup.id.in_(networks))
        return bond_interfaces_query.all()

    @classmethod
    def get_nic_interfaces_for_all_nodes(cls, instance, networks=None):
        nic_interfaces_query = db().query(models.NodeNICInterface).\
            join(models.Node).filter(models.Node.cluster_id == instance.id)
        if networks:
            nic_interfaces_query = nic_interfaces_query.join(
                models.NodeNICInterface.assigned_networks_list, aliased=True).\
                filter(models.NetworkGroup.id.in_(networks))
        return nic_interfaces_query.all()

    @classmethod
    def get_default_group(cls, instance):
        return next(g for g in instance.node_groups if g.is_default)

    @classmethod
    def create_default_group(cls, instance):
        node_group = models.NodeGroup(name=consts.NODE_GROUPS.default,
                                      is_default=True)
        instance.node_groups.append(node_group)
        db.add(node_group)
        db().flush()
        return node_group

    @classmethod
    def get_own_deployment_tasks(
            cls, instance, graph_type=consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE):
        """Return only cluster own deployment graph."""
        cluster_deployment_graph = DeploymentGraph.get_for_model(
            instance, graph_type=graph_type)
        if cluster_deployment_graph:
            return DeploymentGraph.get_tasks(cluster_deployment_graph)
        else:
            return []

    @classmethod
    def _merge_tasks_lists(cls, tasks_lists, validate):
        """Merge several tasks lists.

        Every next list will override tasks in previous one by `task_name` key.

        :param tasks_lists: tasks lists is order of increasing priority
                            task from next will override task in previous
                            if ID is same
        :type tasks_lists: list[list]
        :param validate: function, which will be executed for each task
        :type validate: callable
        :return: merged list
        :rtype: list[dict]
        """
        result = []
        seen = set()
        for task in itertools.chain(*reversed(tasks_lists)):
            if not task['id'] in seen:
                if validate:
                    validate(task)
                seen.add(task['id'])
                result.append(task)
        return result

    @classmethod
    def get_deployment_tasks(cls, instance,
                             graph_type=consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE,
                             validate=None):
        """Return deployment graph for cluster based on cluster attributes

            - if there is deployment_graph defined by user - use it instead of
              defined
            - else return default for release and enabled plugins
              deployment graph
        """
        cluster_deployment_tasks = cls.get_own_deployment_tasks(
            instance, graph_type=graph_type)

        release_deployment_tasks = Release.get_deployment_tasks(
            instance.release, graph_type=graph_type)

        # graph types not supported by plugin manager interface yet
        plugins_deployment_tasks = PluginManager.get_plugins_deployment_tasks(
            instance)

        return cls._merge_tasks_lists([
            release_deployment_tasks,
            plugins_deployment_tasks,
            cluster_deployment_tasks
        ], validate)

    @classmethod
    def get_refreshable_tasks(cls, instance, filter_by_configs=None):
        """Return list of refreshable tasks

        If 'filter_by_configs' specified then only tasks needed to update
        these config resources will be returned as a result, otherwise
        all refreshable tasks will be returned

        :param instance: a Cluster instance
        :param filter_by_configs: a list with configs resources
        :return: list of tasks
        """
        if filter_by_configs:
            filter_by_configs = set(filter_by_configs)
        tasks = []
        for task in cls.get_deployment_tasks(instance):
            refresh_on = task.get(consts.TASK_REFRESH_FIELD)
            if (refresh_on
                and (filter_by_configs is None
                     or filter_by_configs.intersection(set(refresh_on)))):
                tasks.append(task)
        return tasks

    @classmethod
    def get_volumes_metadata(cls, instance):
        """Return proper volumes metadata for cluster

        Metadata consists of general volumes metadata from release
        and volumes metadata from plugins which are releated to this cluster

        :param instance: Cluster DB instance
        :returns: dict -- object with merged volumes metadata
        """
        volumes_metadata = copy.deepcopy(instance.release.volumes_metadata)
        plugin_volumes = PluginManager.get_volumes_metadata(instance)

        volumes_metadata['volumes_roles_mapping'].update(
            plugin_volumes['volumes_roles_mapping'])

        volumes_metadata['volumes'].extend(plugin_volumes['volumes'])

        return volumes_metadata

    @classmethod
    def create_vmware_attributes(cls, instance):
        """Store VmwareAttributes instance into DB."""
        vmware_metadata = instance.release.vmware_attributes_metadata
        if vmware_metadata:
            return VmwareAttributes.create(
                {
                    "editable": vmware_metadata.get("editable"),
                    "cluster_id": instance.id
                }
            )

        return None

    @classmethod
    def get_create_data(cls, instance):
        """Return common parameters cluster was created with.

        This method is compatible with :func:`create` and used to create
        a new cluster with the same settings including the network
        configuration.

        :returns: a dict of key-value pairs as a cluster create data
        """
        data = {
            "name": instance.name,
            "mode": instance.mode,
            "net_provider": instance.net_provider,
            "release_id": instance.release.id,
        }
        data.update(cls.get_network_manager(instance).
                    get_network_config_create_data(instance))
        return data

    @classmethod
    def get_vmware_attributes(cls, instance):
        """Get VmwareAttributes instance from DB.

        Now we have relation with cluster 1:1.
        """
        return db().query(models.VmwareAttributes).filter(
            models.VmwareAttributes.cluster_id == instance.id
        ).first()

    @classmethod
    def get_default_vmware_attributes(cls, instance):
        """Get metadata from release with empty value section."""
        editable = instance.release.vmware_attributes_metadata.get("editable")
        editable = traverse(editable, AttributesGenerator, {
            'cluster': instance,
            'settings': settings,
        })
        return editable

    @classmethod
    def update_vmware_attributes(cls, instance, data):
        """Update Vmware attributes.

        Actually we allways update only value section in editable.
        """
        metadata = instance.vmware_attributes.editable['metadata']
        value = data.get('editable', {}).get('value')
        vmware_attr = {
            'metadata': metadata,
            'value': value
        }
        setattr(instance.vmware_attributes, 'editable', vmware_attr)
        cls.add_pending_changes(instance, "vmware_attributes")
        db().flush()
        vmware_attr.pop('metadata')

        return vmware_attr

    @classmethod
    def is_vmware_enabled(cls, instance):
        """Check if current cluster supports vmware configuration."""
        attributes = cls.get_editable_attributes(instance)
        return attributes.get('common', {}).get('use_vcenter', {}).get('value')

    @staticmethod
    def adjust_nodes_lists_on_controller_removing(instance, nodes_to_delete,
                                                  nodes_to_deploy):
        """Adds controllers to nodes_to_deploy if deleting other controllers

        :param instance: instance of SqlAlchemy cluster
        :param nodes_to_delete: list of nodes to be deleted
        :param nodes_to_deploy: list of nodes to be deployed
        :return:
        """
        if instance is None:
            return

        controllers_ids_to_delete = set([n.id for n in nodes_to_delete
                                         if 'controller' in n.all_roles])
        if controllers_ids_to_delete:
            ids_to_deploy = set([n.id for n in nodes_to_deploy])
            controllers_to_deploy = set(
                filter(lambda n: (n.id not in controllers_ids_to_delete
                                  and n.id not in ids_to_deploy
                                  and 'controller' in n.all_roles),
                       instance.nodes))
            nodes_to_deploy.extend(controllers_to_deploy)

    @classmethod
    def get_repo_urls(self, instance):
        repos = instance.attributes.editable['repo_setup']['repos']['value']
        return tuple(set([r['uri'] for r in repos]))

    @classmethod
    def get_nodes_to_spawn_vms(cls, instance):
        nodes = []
        for node in cls.get_nodes_by_role(instance,
                                          consts.VIRTUAL_NODE_TYPES.virt):
            for vm in node.vms_conf:
                if not vm.get('created'):
                    nodes.append(node)
        return nodes

    @classmethod
    def set_vms_created_state(cls, instance):
        nodes = cls.get_nodes_by_role(instance, consts.VIRTUAL_NODE_TYPES.virt)
        for node in nodes:
            for vm in node.vms_conf:
                if not vm.get('created'):
                    vm['created'] = True
                    # notify about changes
                    node.vms_conf.changed()
        db().flush()

    @classmethod
    def get_network_roles(
            cls, instance, merge_policy=NetworkRoleMergePolicy()):
        """Method for receiving network roles for particular cluster

        :param instance: nailgun.db.sqlalchemy.models.Cluster instance
        :param merge_policy: the policy to merge same roles
        :returns: List of network roles' descriptions
        """
        return PluginManager.get_network_roles(instance, merge_policy)

    @classmethod
    def set_network_template(cls, instance, template):
        instance.network_config.configuration_template = template
        cls.update_nodes_network_template(instance, instance.nodes)
        db().flush()

        if template is None:
            net_manager = cls.get_network_manager(instance)
            for node in instance.nodes:
                net_manager.clear_bond_configuration(node)
                net_manager.assign_networks_by_default(node)

    @classmethod
    def update_nodes_network_template(cls, instance, nodes):
        from nailgun.objects import Node
        template = instance.network_config.configuration_template
        for node in nodes:
            Node.apply_network_template(node, template)

    @classmethod
    def get_nodes_ids(cls, instance):
        return [x[0] for x in db().query(models.Node.id).filter(
            models.Node.cluster_id == instance.id).all()]

    @classmethod
    def get_vips(cls, instance):

        net_roles = cls.get_network_roles(instance)

        cluster_vips = []
        for nr in net_roles:
            cluster_vips.extend(nr['properties']['vip'])

        return cluster_vips

    @classmethod
    def get_assigned_roles(cls, instance):
        """Get list of all roles currently assigned to nodes in cluster

        :param instance: nailgun.db.sqlalchemy.models.Cluster instance
        :returns: List of node roles currently assigned
        """
        pending_roles = db().query(
            sa.func.unnest(models.Node.pending_roles)
        ).filter_by(
            cluster_id=instance.id
        ).distinct().all()
        pending_roles = [pr[0] for pr in pending_roles]

        roles = db().query(
            sa.func.unnest(models.Node.roles)
        ).filter_by(
            cluster_id=instance.id
        ).distinct().all()
        roles = [r[0] for r in roles]

        return set(pending_roles + roles)

    @classmethod
    def is_network_modification_locked(cls, instance):
        """Checks whether network settings can be modified or deleted.

        The result depends on the current status of cluster.
        """
        allowed = [consts.CLUSTER_STATUSES.new,
                   consts.CLUSTER_STATUSES.stopped,
                   consts.CLUSTER_STATUSES.operational,
                   consts.CLUSTER_STATUSES.error]
        return instance.status not in allowed

    @classmethod
    def is_component_enabled(cls, instance, component):
        """Checks is specified additional component enabled in cluster

        :param instance: nailgun.db.sqlalchemy.models.Cluster instance
        :param component: name of additional component
        :returns: The result depends on current component status in settings
        """
        return bool(instance.attributes.editable['additional_components'].
                    get((component), {}).get('value'))

    @classmethod
    def get_networks_to_interfaces_mapping_on_all_nodes(cls, instance):
        """Query networks to interfaces mapping on all nodes in cluster.

        Returns combined results for NICs and bonds for every node.
        Names are returned for node and interface (NIC or bond),
        IDs are returned for networks. Results are sorted by node name then
        interface name.
        """
        nodes_nics_networks = db().query(
            models.Node.hostname,
            models.NodeNICInterface.name,
            models.NetworkGroup.id,
        ).join(
            models.Node.nic_interfaces,
            models.NodeNICInterface.assigned_networks_list
        ).filter(
            models.Node.cluster_id == instance.id,
        )
        nodes_bonds_networks = db().query(
            models.Node.hostname,
            models.NodeBondInterface.name,
            models.NetworkGroup.id,
        ).join(
            models.Node.bond_interfaces,
            models.NodeBondInterface.assigned_networks_list
        ).filter(
            models.Node.cluster_id == instance.id,
        )
        return nodes_nics_networks.union(
            nodes_bonds_networks
        ).order_by(
            # column 1 then 2 from the result. cannot call them by name as
            # names for column 2 are different in this union
            '1', '2'
        )

    @classmethod
    def get_nodes_to_update_config(cls, cluster, node_id=None, node_role=None,
                                   only_ready_nodes=True):
        """Get nodes for specified cluster that should be updated.

        Configuration update can be executed for all nodes in the cluster,
        or for single node, or for all nodes with specified role.
        If :param only_ready_nodes set by True function returns list of nodes
        that will be updated during next config update execution.
        If :param only_ready_nodes set by False function returns list of all
        nodes that will finally get an updated configuration.
        """
        query = cls.get_nodes_not_for_deletion(cluster)

        if only_ready_nodes:
            query = query.filter_by(status=consts.NODE_STATUSES.ready)
        if node_id:
            query = query.filter_by(id=node_id)
        elif node_role:
            query = query.filter(
                models.Node.roles.any(node_role))

        return query.all()

    @classmethod
    def prepare_for_deployment(cls, instance, nodes=None):
        """Shortcut for NetworkManager.prepare_for_deployment.

        :param instance: nailgun.db.sqlalchemy.models.Cluster instance
        :param nodes: the list of Nodes, None means for all nodes
        """
        cls.get_network_manager(instance).prepare_for_deployment(
            instance, instance.nodes if nodes is None else nodes
        )

    @classmethod
    def prepare_for_provisioning(cls, instance, nodes=None):
        """Shortcut for NetworkManager.prepare_for_provisioning.

        :param instance: nailgun.db.sqlalchemy.models.Cluster instance
        :param nodes: the list of Nodes, None means for all nodes
        """
        cls.get_network_manager(instance).prepare_for_provisioning(
            instance.nodes if nodes is None else nodes
        )

    @classmethod
    def has_compute_vmware_changes(cls, instance):
        """Checks if any 'compute-vmware' nodes are waiting for deployment.

        :param instance: cluster for checking
        :type instance: nailgun.db.sqlalchemy.models.Cluster instance
        """
        compute_vmware_nodes_query = db().query(models.Node).filter_by(
            cluster_id=instance.id
        ).filter(sa.or_(
            sa.and_(models.Node.roles.any('compute-vmware'),
                    models.Node.pending_deletion),
            models.Node.pending_roles.any('compute-vmware')
        ))
        return db().query(compute_vmware_nodes_query.exists()).scalar()

    @classmethod
    def get_operational_vmware_compute_nodes(cls, instance):
        return db().query(models.Node).filter_by(
            cluster_id=instance.id
        ).filter(
            models.Node.roles.any('compute-vmware'),
            sa.not_(models.Node.pending_deletion)
        ).all()

    @classmethod
    def is_task_deploy_enabled(cls, instance):
        """Tests that task based deploy is enabled.

        :param instance: cluster for checking
        :type instance: nailgun.db.sqlalchemy.models.Cluster instance
        """
        attrs = cls.get_editable_attributes(instance, False)
        return attrs['common'].get('task_deploy', {}).get('value')

    # FIXME(aroma): remove updating of 'deployed_before'
    # when stop action is reworked. 'deployed_before'
    # flag identifies whether stop action is allowed for the
    # cluster. Please, refer to [1] for more details.
    # [1]: https://bugs.launchpad.net/fuel/+bug/1529691
    @classmethod
    def set_deployed_before_flag(cls, instance, value):
        """Change value for before_deployed if needed

        :param instance: nailgun.db.sqlalchemy.models.Cluster instance
        :param value: new value for flag
        :type value: bool
        """
        generated = copy.deepcopy(instance.attributes.generated)

        if 'deployed_before' not in generated:
            # NOTE(aroma): this is needed for case when master node has
            # been upgraded and there is attempt to re/deploy previously
            # existing clusters. As long as setting the flag is temporary
            # solution data base migration code should not be mangled
            # in order to support it
            generated['deployed_before'] = {'value': value}
        elif generated['deployed_before']['value'] != value:
            generated['deployed_before']['value'] = value

        instance.attributes.generated = generated
        db.flush()

    @classmethod
    def get_nodes_count_unmet_status(cls, instance, status):
        """Gets the number of nodes, that does not have specified status.

        :param instance: nailgun.db.sqlalchemy.models.Cluster instance
        :param status: the expected status
        :return: the number of nodes that does not have specified status
        """

        q = db().query(models.Node).filter_by(cluster_id=instance.id)
        return q.filter(models.Node.status != status).count()

    @classmethod
    def get_network_groups_and_node_ids(cls, instance_id):
        """Get network group information for the given cluster

        The admin network group will not be included.

        :param instance: Cluster instance
        :type instance: nailgun.db.sqlalchemy.models.Cluster instance
        :returns: tuple of Node ID, and NetworkGroup ID, name, meta
        """
        query = (db().query(
            models.Node.id,
            models.NetworkGroup.id,
            models.NetworkGroup.name,
            models.NetworkGroup.meta)
            .join(models.NodeGroup.nodes)
            .join(models.NodeGroup.networks)
            .filter(models.NodeGroup.cluster_id == instance_id,
                    models.NetworkGroup.name != consts.NETWORKS.fuelweb_admin)
        )

        return query


class ClusterCollection(NailgunCollection):
    """Cluster collection."""

    #: Single Cluster object class
    single = Cluster


class VmwareAttributes(NailgunObject):
    model = models.VmwareAttributes

    @staticmethod
    def get_nova_computes_attrs(attributes):
        return attributes.get('value', {}).get(
            'availability_zones', [{}])[0].get('nova_computes', [])

    @classmethod
    def get_nova_computes_target_nodes(cls, instance):
        """Get data of targets node for all nova computes.

        :param instance: nailgun.db.sqlalchemy.models.Cluster instance
        :returns: list of dicts that represents nova compute targets
        """
        nova_compute_target_nodes = []
        for nova_compute in cls.get_nova_computes_attrs(instance.editable):
            target = nova_compute['target_node']['current']
            if target['id'] != 'controllers':
                nova_compute_target_nodes.append(target)
        return nova_compute_target_nodes
