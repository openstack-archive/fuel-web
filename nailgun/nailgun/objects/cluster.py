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

from sqlalchemy import or_
import yaml

from nailgun.objects.serializers.cluster import ClusterSerializer
from nailgun.orchestrator import graph_configuration

from nailgun import consts

from nailgun.db import db

from nailgun.db.sqlalchemy import models

from nailgun.errors import errors

from nailgun.logger import logger

from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects import Release

from nailgun.plugins.manager import PluginManager

from nailgun.settings import settings

from nailgun.utils import AttributesGenerator
from nailgun.utils import dict_merge
from nailgun.utils import generate_editables
from nailgun.utils import traverse


class Attributes(NailgunObject):
    """Cluster attributes object
    """

    #: SQLAlchemy model for Cluster attributes
    model = models.Attributes

    @classmethod
    def generate_fields(cls, instance):
        """Generate field values for Cluster attributes using
        generators.

        :param instance: Attributes instance
        :returns: None
        """
        instance.generated = traverse(
            instance.generated,
            AttributesGenerator
        )

    @classmethod
    def merged_attrs(cls, instance):
        """Generates merged dict which includes generated Cluster
        attributes recursively updated by new values from editable
        attributes.

        :param instance: Attributes instance
        :returns: dict of merged attributes
        """
        return dict_merge(
            instance.generated,
            instance.editable
        )

    @classmethod
    def merged_attrs_values(cls, instance):
        """Transforms raw dict of attributes returned by :func:`merged_attrs`
        into dict of facts for sending to orchestrator.

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
    """Cluster object
    """

    #: SQLAlchemy model for Cluster
    model = models.Cluster

    #: Serializer for Cluster
    serializer = ClusterSerializer

    #: Cluster JSON schema
    schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "title": "Cluster",
        "description": "Serialized Cluster object",
        "type": "object",
        "properties": {
            "id": {"type": "number"},
            "name": {"type": "string"},
            "mode": {
                "type": "string",
                "enum": list(consts.CLUSTER_MODES)
            },
            "status": {
                "type": "string",
                "enum": list(consts.CLUSTER_STATUSES)
            },
            "net_provider": {
                "type": "string",
                "enum": list(consts.CLUSTER_NET_PROVIDERS)
            },
            "grouping": {
                "type": "string",
                "enum": list(consts.CLUSTER_GROUPING)
            },
            "release_id": {"type": "number"},
            "pending_release_id": {"type": "number"},
            "replaced_deployment_info": {"type": "object"},
            "replaced_provisioning_info": {"type": "object"},
            "is_customized": {"type": "boolean"},
            "fuel_version": {"type": "string"}
        }
    }

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

        #TODO(enchantner): fix this temporary hack in clients
        if "release_id" not in data:
            release_id = data.pop("release", None)
            data["release_id"] = release_id

        assign_nodes = data.pop("nodes", [])

        data["fuel_version"] = settings.VERSION["release"]
        new_cluster = super(Cluster, cls).create(data)
        cls.create_default_group(new_cluster)

        cls.create_attributes(new_cluster)

        try:
            cls.get_network_manager(new_cluster).\
                create_network_groups_and_config(new_cluster, data)
            cls.add_pending_changes(new_cluster, "attributes")
            cls.add_pending_changes(new_cluster, "networks")

            if assign_nodes:
                cls.update_nodes(new_cluster, assign_nodes)

        except (
            errors.OutOfVLANs,
            errors.OutOfIPs,
            errors.NoSuitableCIDR,
            errors.InvalidNetworkPool
        ) as exc:
            db().delete(new_cluster)
            raise errors.CannotCreate(exc.message)

        db().flush()

        return new_cluster

    @classmethod
    def get_default_kernel_params(cls, instance):
        kernel_params = instance.attributes.editable.get("kernel_params")
        if kernel_params and kernel_params.get("kernel"):
            return kernel_params.get("kernel").get("value")

    @classmethod
    def create_attributes(cls, instance):
        """Create attributes for current Cluster instance and
        generate default values for them
        (see :func:`Attributes.generate_fields`)

        :param instance: Cluster instance
        :returns: None
        """
        attributes = Attributes.create(
            {
                "editable": cls.get_default_editable_attributes(instance),
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
    def get_default_editable_attributes(cls, instance):
        """Get editable attributes from release metadata

        :param instance: Cluster instance
        :returns: Dict object
        """
        editable = instance.release.attributes_metadata.get("editable")
        generate_editables(editable, AttributesGenerator)
        # when attributes created we need to understand whether should plugin
        # be applied for created cluster
        plugin_attrs = PluginManager.get_plugin_attributes(instance)
        editable = dict(plugin_attrs, **editable)
        return editable

    @classmethod
    def get_attributes(cls, instance):
        """Get attributes for current Cluster instance

        :param instance: Cluster instance
        :returns: Attributes instance
        """
        return db().query(models.Attributes).filter(
            models.Attributes.cluster_id == instance.id
        ).first()

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
        db().flush()

    @classmethod
    def get_editable_attributes(cls, instance):
        attrs = cls.get_attributes(instance)
        editable = attrs.editable
        return {'editable': editable}

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

        if instance.net_provider == 'neutron':
            from nailgun.network.neutron import NeutronManager
            return NeutronManager
        else:
            from nailgun.network.nova_network import NovaNetworkManager
            return NovaNetworkManager

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

        #TODO(enchantner): check if node belongs to cluster
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
        """Update Cluster object instance with specified parameters in DB.
        If "nodes" are specified in data then they will replace existing ones
        (see :func:`update_nodes`)

        :param instance: Cluster instance
        :param data: dictionary of key-value pairs as object fields
        :returns: Cluster instance
        """
        # fuel_version cannot be changed
        data.pop("fuel_version", None)

        nodes = data.pop("nodes", None)
        changes = data.pop("changes", None)

        super(Cluster, cls).update(instance, data)
        if nodes is not None:
            cls.update_nodes(instance, nodes)
        if changes is not None:
            cls.update_changes(instance, changes)
        return instance

    @classmethod
    def update_nodes(cls, instance, nodes_ids):
        """Update Cluster nodes by specified node IDs.
        Nodes with specified IDs will replace existing ones in Cluster

        :param instance: Cluster instance
        :param nodes_ids: list of nodes ids
        :returns: None
        """

        # TODO(NAME): sepatate nodes
        #for deletion and addition by set().
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
        map(
            net_manager.assign_networks_by_default,
            nodes_to_add
        )
        db().flush()

    @classmethod
    def update_changes(cls, instance, changes):
        instance.changes_list = [
            models.ClusterChanges(**change) for change in changes
        ]
        db().flush()

    @classmethod
    def get_ifaces_for_network_in_cluster(
            cls, instance, net):
        """Method for receiving node_id:iface pairs for all nodes in
        specific cluster

        :param instance: Cluster instance
        :param net: Nailgun specific network name
        :type net: str
        :returns: List of node_id, iface pairs for all nodes in cluster.
        """
        nics_db = db().query(
            models.NodeNICInterface.node_id,
            models.NodeNICInterface.name).filter(
                models.NodeNICInterface.node.has(cluster_id=instance.id),
                models.NodeNICInterface.assigned_networks_list.any(name=net)
            )
        bonds_db = db().query(
            models.NodeBondInterface.node_id,
            models.NodeBondInterface.name).filter(
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
        """Determine whether Public network is to be assigned to all nodes in
        this cluster.

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
    def set_primary_role(cls, intance, nodes, role_name):
        """Method for assigning primary attribute for specific role.
        - verify that there is no primary attribute of specific role
        assigned to cluster nodes with this role in role list
        or pending role list, and this node is not marked for deletion
        - if there is no primary role assigned, filter nodes which have current
        role in roles_list or pending_role_list
        - if there is nodes with ready state - they should have higher priority
        - if role was in primary_role_list - change primary attribute
        for that association, same for role_list, this is required
        because deployment_serializer used by cli to generate deployment info

        :param instance: Cluster db objects
        :param nodes: list of Node db objects
        :param role_name: string with known role name
        """
        all_roles = intance.release.role_list
        role = next((r for r in all_roles if r.name == role_name), None)
        if role is None:
            logger.warning(
                'Trying to assign primary for non-existing role %s', role_name)
            return
        node = db().query(models.Node).filter_by(
            pending_deletion=False).filter(or_(
                models.Node.role_associations.any(role=role.id, primary=True),
                models.Node.pending_role_associations.any(
                    role=role.id, primary=True))).filter(
                        models.Node.cluster == intance).first()
        if not node:
            filtered_nodes = []
            for node in nodes:
                if (not node.pending_deletion and (
                        role in node.role_list
                        or role in node.pending_role_list)):
                    filtered_nodes.append(node)
            filtered_nodes = sorted(filtered_nodes, key=lambda node: node.id)
            if filtered_nodes:
                primary_node = next((
                    node for node in filtered_nodes
                    if node.status == consts.NODE_STATUSES.ready),
                    filtered_nodes[0])
                if role in primary_node.role_list:
                    associations = primary_node.role_associations
                elif role in primary_node.pending_role_list:
                    associations = primary_node.pending_role_associations
                else:
                    logger.warning((
                        'Role %s neither in pending, nor role.'
                        ' You hit strange bug'), role_name)
                    return
                for assoc in associations:
                    if assoc.role == role.id:
                        assoc.primary = True
        db().flush()

    @classmethod
    def set_primary_roles(cls, instance, nodes):
        """Idempotent method for assignment of all primary attribute
        for all roles that requires it.
        To mark role as primary add has_primary: true attribute to release

        :param instance: Cluster db object
        :param nodes: list of Node db objects
        """
        if not instance.is_ha_mode:
            return
        roles_metadata = instance.release.roles_metadata
        for role, meta in roles_metadata.items():
            if meta.get('has_primary'):
                cls.set_primary_role(instance, nodes, role)

    @classmethod
    def get_all_controllers(cls, instance):
        roles_id = db().query(models.Role).\
            filter_by(release_id=instance.release_id).\
            filter_by(name='controller').first().id
        deployed_controllers = db().query(models.Node).filter_by(
            cluster_id=instance.id).join(models.Node.role_list, aliased=True).\
            filter(models.Role.id == roles_id).all()
        pending_controllers = db().query(models.Node).\
            filter_by(cluster_id=instance.id).\
            join(models.Node.pending_role_list, aliased=True).\
            filter(models.Role.id == roles_id).all()
        return deployed_controllers + pending_controllers

    @classmethod
    def get_controllers_group_id(cls, instance):
        roles_id = db().query(models.Role).filter_by(
            release_id=instance.release_id).\
            filter_by(name='controller').first().id
        controller = db().query(models.Node).\
            filter_by(cluster_id=instance.id).\
            filter(False == models.Node.pending_deletion).\
            join(models.Node.role_list, aliased=True).\
            filter(models.Role.id == roles_id).first()
        if not controller or not controller.group_id:
            controller = db().query(models.Node).\
                filter(False == models.Node.pending_deletion).\
                filter_by(cluster_id=instance.id).\
                join(models.Node.pending_role_list, aliased=True).\
                filter(models.Role.id == roles_id).first()
        if controller and controller.group_id:
            return controller.group_id
        return cls.get_default_group(instance).id

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
        return [g for g in instance.node_groups
                if g.name == consts.NODE_GROUPS.default][0]

    @classmethod
    def create_default_group(cls, instance):
        node_group = models.NodeGroup(name=consts.NODE_GROUPS.default)
        instance.node_groups.append(node_group)
        db.add(node_group)
        db().flush()
        return node_group

    @classmethod
    def get_deployment_tasks(cls, instance):
        """Return deployment graph for cluster based on cluster attributes

            - if there is deployment_graph defined by user - use it instead of
              defined
            - if instance assigned for patching - return custom patching graph
            - else return default for release deployment graph
        """
        if instance.deployment_tasks:
            return instance.deployment_tasks
        elif instance.pending_release_id:
            return yaml.load(graph_configuration.PATCHING)
        else:
            return Release.get_deployment_tasks(instance.release)


class ClusterCollection(NailgunCollection):
    """Cluster collection
    """

    #: Single Cluster object class
    single = Cluster
