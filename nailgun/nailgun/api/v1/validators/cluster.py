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

import copy
from distutils.version import StrictVersion
from itertools import groupby

import six
import sqlalchemy as sa

from nailgun.api.v1.validators.base import BaseDefferedTaskValidator
from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema import cluster as cluster_schema
from nailgun.api.v1.validators.node import ProvisionSelectedNodesValidator

from nailgun import consts

from nailgun.db import db
from nailgun.db.sqlalchemy.models import Node
from nailgun.errors import errors
from nailgun import objects
from nailgun.utils import is_objects_equal
from nailgun.utils import restrictions


class ClusterValidator(BasicValidator):

    single_schema = cluster_schema.single_schema
    collection_schema = cluster_schema.collection_schema

    _blocked_for_update = (
        'net_provider',
    )

    @classmethod
    def _can_update_release(cls, curr_release, pend_release):
        return any([
            # redeploy
            curr_release.id == pend_release.id,

            # update to upper release
            curr_release.operating_system == pend_release.operating_system
            and curr_release.version in pend_release.can_update_from_versions,

            # update to lower release
            curr_release.operating_system == pend_release.operating_system
            and pend_release.version in curr_release.can_update_from_versions,
        ])

    @classmethod
    def _validate_common(cls, data, instance=None):
        d = cls.validate_json(data)
        release_id = d.get("release", d.get("release_id"))
        if release_id:
            release = objects.Release.get_by_uid(release_id)
            if not release:
                raise errors.InvalidData(
                    "Invalid release ID", log_message=True)
            if not objects.Release.is_deployable(release):
                raise errors.NotAllowed(
                    "Release with ID '{0}' is not deployable.".format(
                        release_id), log_message=True)
            cls._validate_mode(d, release)

        pend_release_id = d.get("pending_release_id")
        if pend_release_id:
            pend_release = objects.Release.get_by_uid(pend_release_id,
                                                      fail_if_not_found=True)
            if not release_id:
                if not instance:
                    raise errors.InvalidData(
                        "Cannot set pending release when "
                        "there is no current release",
                        log_message=True
                    )
                release_id = instance.release_id
            curr_release = objects.Release.get_by_uid(release_id)

            if not cls._can_update_release(curr_release, pend_release):
                raise errors.InvalidData(
                    "Cannot set pending release as "
                    "it cannot update current release",
                    log_message=True
                )

        return d

    @classmethod
    def _validate_components(cls, release_id, components_list):
        release = objects.Release.get_by_uid(release_id)
        release_components = objects.Release.get_all_components(release)
        components_set = set(components_list)
        found_release_components = [
            c for c in release_components if c['name'] in components_set]
        found_release_components_names_set = set(
            c['name'] for c in found_release_components)

        if found_release_components_names_set != components_set:
            raise errors.InvalidData(
                u'{0} components are not related to release "{1}".'.format(
                    sorted(
                        components_set - found_release_components_names_set),
                    release.name
                ),
                log_message=True
            )

        mandatory_component_types = set(['hypervisor', 'network', 'storage'])
        for component in found_release_components:
            component_name = component['name']
            for incompatible in component.get('incompatible', []):
                incompatible_component_names = list(
                    cls._resolve_names_for_dependency(
                        components_set, incompatible))
                if incompatible_component_names:
                    raise errors.InvalidData(
                        u"Incompatible components were found: "
                        u"'{0}' incompatible with {1}.".format(
                            component_name, incompatible_component_names),
                        log_message=True
                    )

            component_type = lambda x: x['name'].split(':', 1)[0]
            for c_type, group in groupby(
                    sorted(component.get('requires', []), key=component_type),
                    component_type):
                group_components = list(group)
                for require in group_components:
                    component_exist = any(
                        cls._resolve_names_for_dependency(
                            components_set, require))
                    if component_exist:
                        break
                else:
                    raise errors.InvalidData(
                        u"Requires {0} for '{1}' components were not "
                        u"satisfied.".format(
                            [c['name'] for c in group_components],
                            component_name),
                        log_message=True
                    )
            if component_type(component) in mandatory_component_types:
                mandatory_component_types.remove(component_type(component))

        if mandatory_component_types:
            raise errors.InvalidData(
                "Components with {0} types required but wasn't found in data"
                .format(sorted(mandatory_component_types)),
                log_message=True
            )

    @staticmethod
    def _resolve_names_for_dependency(components_set, dependency):
        prefix = dependency['name'].split('*', 1)[0]
        return (name for name in components_set if name.startswith(prefix))

    @classmethod
    def validate(cls, data):
        d = cls._validate_common(data)

        # TODO(ikalnitsky): move it to _validate_common when
        # PATCH method will be implemented
        release_id = d.get("release", d.get("release_id", None))
        if not release_id:
            raise errors.InvalidData(
                u"Release ID is required", log_message=True)

        if "name" in d:
            if objects.ClusterCollection.filter_by(
                    None, name=d["name"]).first():
                raise errors.AlreadyExists(
                    "Environment with this name already exists",
                    log_message=True
                )

        if "components" in d:
            cls._validate_components(release_id, d['components'])

        return d

    @classmethod
    def validate_update(cls, data, instance):
        d = cls._validate_common(data, instance=instance)

        if "name" in d:
            query = objects.ClusterCollection.filter_by_not(
                None, id=instance.id)

            if objects.ClusterCollection.filter_by(
                    query, name=d["name"]).first():
                raise errors.AlreadyExists(
                    "Environment with this name already exists",
                    log_message=True
                )

        for k in cls._blocked_for_update:
            if k in d and getattr(instance, k) != d[k]:
                raise errors.InvalidData(
                    u"Changing '{0}' for environment is prohibited".format(k),
                    log_message=True
                )

        cls._validate_mode(d, instance.release)
        if 'nodes' in d:
            # Here d['nodes'] is list of node IDs
            # to be assigned to the cluster.
            cls._validate_nodes(d['nodes'], instance)

        return d

    @classmethod
    def _validate_mode(cls, data, release):
        mode = data.get("mode")
        if mode and mode not in release.modes:
            modes_list = ', '.join(release.modes)
            raise errors.InvalidData(
                "Cannot deploy in {0} mode in current release."
                " Need to be one of: {1}".format(
                    mode, modes_list),
                log_message=True
            )

    @classmethod
    def _validate_nodes(cls, new_node_ids, instance):
        set_new_node_ids = set(new_node_ids)
        set_old_node_ids = set(objects.Cluster.get_nodes_ids(instance))
        nodes_to_add = set_new_node_ids - set_old_node_ids
        nodes_to_remove = set_old_node_ids - set_new_node_ids

        hostnames_to_add = [x[0] for x in db.query(Node.hostname)
                            .filter(Node.id.in_(nodes_to_add)).all()]

        duplicated = [x[0] for x in db.query(Node.hostname).filter(
            sa.and_(
                Node.hostname.in_(hostnames_to_add),
                Node.cluster_id == instance.id,
                Node.id.notin_(nodes_to_remove)
            )
        ).all()]
        if duplicated:
            raise errors.AlreadyExists(
                "Nodes with hostnames [{0}] already exist in cluster {1}."
                .format(",".join(duplicated), instance.id)
            )


class AttributesValidator(BasicValidator):

    @classmethod
    def validate(cls, data, cluster=None):
        d = cls.validate_json(data)
        if "generated" in d:
            raise errors.InvalidData(
                "It is not allowed to update generated attributes",
                log_message=True
            )
        if "editable" in d and not isinstance(d["editable"], dict):
            raise errors.InvalidData(
                "Editable attributes should be a dictionary",
                log_message=True
            )

        attrs = d
        if cluster is not None:
            attrs = objects.Cluster.get_updated_editable_attributes(cluster, d)

            cls._validate_net_provider(attrs, cluster)

            # NOTE(agordeev): disable classic provisioning for 7.0 or higher
            if StrictVersion(cluster.release.environment_version) >= \
                    StrictVersion(consts.FUEL_IMAGE_BASED_ONLY):
                provision_data = attrs['editable'].get('provision')
                if provision_data:
                    if provision_data['method']['value'] != \
                            consts.PROVISION_METHODS.image:
                        raise errors.InvalidData(
                            u"Cannot use classic provisioning for adding "
                            u"nodes to environment",
                            log_message=True)
                else:
                    raise errors.InvalidData(
                        u"Provisioning method is not set. Unable to continue",
                        log_message=True)

            cls.validate_plugin_attributes(
                cluster, attrs.get('editable', {})
            )

        cls.validate_editable_attributes(attrs)

        return d

    @classmethod
    def _validate_net_provider(cls, data, cluster):
        common_attrs = data.get('editable', {}).get('common', {})
        net_provider = cluster.net_provider

        if common_attrs.get('use_vcenter', {}).get('value') is True and \
                net_provider != consts.CLUSTER_NET_PROVIDERS.nova_network:
                    raise errors.InvalidData(u'vCenter requires Nova Network '
                                             'to be set as a network provider',
                                             log_message=True)

    @classmethod
    def validate_editable_attributes(cls, data):
        """Validate 'editable' attributes."""
        for attrs in data.get('editable', {}).values():
            if not isinstance(attrs, dict):
                continue
            for attr_name, attr in six.iteritems(attrs):
                cls.validate_attribute(attr_name, attr)

        return data

    @classmethod
    def validate_attribute(cls, attr_name, attr):
        """Validates a single attribute from settings.yaml.

        Dict is of this form:

        description: <description>
        label: <label>
        restrictions:
          - <restriction>
          - <restriction>
          - ...
        type: <type>
        value: <value>
        weight: <weight>
        regex:
          error: <error message>
          source: <regexp source>

        We validate that 'value' corresponds to 'type' according to
        attribute_type_schemas mapping in json_schema/cluster.py.
        If regex is present, we additionally check that the provided string
        value matches the regexp.

        :param attr_name: Name of the attribute being checked
        :param attr: attribute value
        :return: attribute or raise InvalidData exception
        """

        if not isinstance(attr, dict):
            return attr

        if 'type' not in attr and 'value' not in attr:
            return attr

        schema = copy.deepcopy(cluster_schema.attribute_schema)
        type_ = attr.get('type')
        if type_:
            value_schema = cluster_schema.attribute_type_schemas.get(type_)
            if value_schema:
                schema['properties'].update(value_schema)

        try:
            cls.validate_schema(attr, schema)
        except errors.InvalidData as e:
            raise errors.InvalidData('[{0}] {1}'.format(attr_name, e.message))

        # Validate regexp only if some value is present
        # Otherwise regexp might be invalid
        if attr['value']:
            regex_err = restrictions.AttributesRestriction.validate_regex(attr)
            if regex_err is not None:
                raise errors.InvalidData(
                    '[{0}] {1}'.format(attr_name, regex_err))

    @classmethod
    def validate_plugin_attributes(cls, cluster, attributes):
        """Validates Cluster-Plugins relations attributes

        :param cluster: A cluster instance
        :type cluster: nailgun.objects.cluster.Cluster
        :param attributes: The editable attributes of the Cluster
        :type attributes: dict
        :raises: errors.NotAllowed
        """

        # TODO(need to enable restrictions check for cluster attributes[1])
        # [1] https://bugs.launchpad.net/fuel/+bug/1519904
        # Validates only that plugin can be installed on deployed env.
        if not cluster.is_locked:
            return

        enabled_plugins = set(
            p.id for p in objects.ClusterPlugins.get_enabled(cluster.id)
        )

        for attrs in six.itervalues(attributes):
            if not isinstance(attrs, dict):
                continue

            plugin_versions = attrs.get('plugin_versions', None)
            if plugin_versions is None:
                continue

            if not attrs.get('metadata', {}).get('enabled'):
                continue

            for version in plugin_versions['values']:
                plugin_id = version.get('data')
                plugin = objects.Plugin.get_by_uid(plugin_id)
                if not plugin:
                    continue

                if plugin_id != plugin_versions['value']:
                    continue

                if plugin.is_hotpluggable or plugin.id in enabled_plugins:
                    break

                raise errors.NotAllowed(
                    "This plugin version can be enabled only "
                    "before environment is deployed.",
                    log_message=True
                )


class ClusterChangesValidator(BaseDefferedTaskValidator):

    @classmethod
    def validate(cls, cluster):
        cls.validate_release(cluster=cluster)
        ProvisionSelectedNodesValidator.validate_provision(None, cluster)


class VmwareAttributesValidator(BasicValidator):

    single_schema = cluster_schema.vmware_attributes_schema

    @staticmethod
    def _get_target_node_id(nova_compute_data):
        return nova_compute_data['target_node']['current']['id']

    @classmethod
    def _validate_updated_attributes(cls, attributes, instance):
        """Validate that attributes contains changes only for allowed fields.

        :param attributes: new vmware attribute settings for db instance
        :param instance: nailgun.db.sqlalchemy.models.VmwareAttributes instance
        """
        def _check_attribute(metadata, attributes, new_attributes):
            if type(attributes) != type(new_attributes):
                raise errors.InvalidData(
                    "Value type of '{0}' attribute couldn't be changed.".
                    format(metadata.get('label') or metadata.get('name')),
                    log_message=True
                )
            if metadata.get('editable_for_deployed'):
                return True

            if 'fields' not in metadata:
                if not is_objects_equal(attributes, new_attributes):
                    raise errors.InvalidData(
                        "Value of '{0}' attribute couldn't be changed.".
                        format(metadata.get('label') or metadata.get('name')),
                        log_message=True
                    )
                return True

            fields_sort_functions = {
                'availability_zones': lambda x: x['az_name'],
                'nova_computes': lambda x: x['vsphere_cluster']
            }
            field_name = metadata['name']
            if isinstance(attributes, (list, tuple)):
                if len(attributes) != len(new_attributes):
                    raise errors.InvalidData(
                        "Value of '{0}' attribute couldn't be changed.".
                        format(metadata.get('label') or metadata.get('name')),
                        log_message=True
                    )
                attributes = sorted(
                    attributes, key=fields_sort_functions.get(field_name))
                new_attributes = sorted(
                    new_attributes, key=fields_sort_functions.get(field_name))
                for item, new_item in zip(attributes, new_attributes):
                    for field_metadata in metadata['fields']:
                        _check_attribute(field_metadata,
                                         item.get(field_metadata['name']),
                                         new_item.get(field_metadata['name']))
            elif isinstance(attributes, dict):
                for field_metadata in metadata['fields']:
                    _check_attribute(field_metadata,
                                     attributes.get(field_name, {}),
                                     new_attributes.get(field_name, {}))

        metadata = instance.editable.get('metadata', {})
        db_editable_attributes = instance.editable.get('value', {})
        new_editable_attributes = attributes.get('editable', {}).get('value')
        for attribute_metadata in metadata:
            attribute_name = attribute_metadata['name']
            _check_attribute(attribute_metadata,
                             db_editable_attributes.get(attribute_name),
                             new_editable_attributes.get(attribute_name))

    @classmethod
    def _validate_nova_computes(cls, attributes, instance):
        """Validates a 'nova_computes' attributes from vmware_attributes

        Raise InvalidData exception if new attributes is not valid.

        :param instance: nailgun.db.sqlalchemy.models.VmwareAttributes instance
        :param attributes: new attributes for db instance for validation
        """
        input_nova_computes = objects.VmwareAttributes.get_nova_computes_attrs(
            attributes.get('editable'))

        cls.check_nova_compute_duplicate_and_empty_values(input_nova_computes)

        db_nova_computes = objects.VmwareAttributes.get_nova_computes_attrs(
            instance.editable)
        if instance.cluster.is_locked:
            cls.check_operational_controllers_settings(input_nova_computes,
                                                       db_nova_computes)
        operational_compute_nodes = [
            n for n in instance.cluster.nodes if
            'compute-vmware' in n.roles and not n.pending_deletion]
        cls.check_operational_node_settings(
            input_nova_computes, db_nova_computes, operational_compute_nodes)

    @classmethod
    def check_nova_compute_duplicate_and_empty_values(cls, attributes):
        """Check 'nova_computes' attributes for empty and duplicate values."""
        nova_compute_attributes_sets = {
            'vsphere_cluster': set(),
            'service_name': set(),
            'target_node': set()
        }
        for nova_compute_data in attributes:
            for attr, values in six.iteritems(nova_compute_attributes_sets):
                if attr == 'target_node':
                    settings_value = cls._get_target_node_id(nova_compute_data)
                    if settings_value == 'controllers':
                        continue
                else:
                    settings_value = nova_compute_data.get(attr)
                if not settings_value:
                    raise errors.InvalidData(
                        "Empty value for attribute '{0}' is not allowed".
                        format(attr),
                        log_message=True
                    )
                if settings_value in values:
                    raise errors.InvalidData(
                        "Duplicate value '{0}' for attribute '{1}' is "
                        "not allowed".format(settings_value, attr),
                        log_message=True
                    )
                values.add(settings_value)

    @classmethod
    def check_operational_node_settings(cls, input_nova_computes,
                                        db_nova_computes, operational_nodes):
        """Validates a 'nova_computes' attributes for operational compute nodes

        Raise InvalidData exception if nova_compute settings will be changed or
        deleted for deployed nodes with role 'compute-vmware' that wasn't mark
        for deletion

        :param input_nova_computes: new nova_compute attributes
        :param db_nova_computes: nova_computes attributes stored in db
        :param operational_nodes: list of operation vmware-compute nodes
        """
        input_computes_by_node_name = dict(
            (cls._get_target_node_id(nc), nc) for nc in input_nova_computes)
        db_computes_by_node_name = dict(
            (cls._get_target_node_id(nc), nc) for nc in db_nova_computes)

        for node in operational_nodes:
            node_hostname = node.hostname
            input_nova_compute = input_computes_by_node_name.get(node_hostname)
            if not input_nova_compute:
                raise errors.InvalidData(
                    "The following compute-vmware node couldn't be "
                    "deleted from vSphere cluster: {0}".format(node.name),
                    log_message=True
                )
            db_nova_compute = db_computes_by_node_name.get(node_hostname)
            for attr, db_value in six.iteritems(db_nova_compute):
                if attr != 'target_node' and \
                        db_value != input_nova_compute.get(attr):
                    raise errors.InvalidData(
                        "Parameter '{0}' of nova compute instance of vSphere "
                        "cluster '{1}' couldn't be changed".format(
                            attr, db_nova_compute['vsphere_cluster']),
                        log_message=True
                    )

    @classmethod
    def check_operational_controllers_settings(cls, input_nova_computes,
                                               db_nova_computes):
        """Check deployed nova computes settings with target = controllers.

        Raise InvalidData exception if any deployed nova computes clusters with
        target 'controllers' were added, removed or modified.

        :param input_nova_computes: new nova_compute settings
        :param db_nova_computes: nova_computes settings stored in db
        """
        input_computes_by_vsphere_name = dict(
            (nc['vsphere_cluster'], nc) for nc in input_nova_computes if
            cls._get_target_node_id(nc) == 'controllers'
        )
        db_clusters_names = set()
        for db_nova_compute in db_nova_computes:
            target_name = cls._get_target_node_id(db_nova_compute)
            if target_name == 'controllers':
                vsphere_name = db_nova_compute['vsphere_cluster']
                input_nova_compute = \
                    input_computes_by_vsphere_name.get(vsphere_name)
                if not input_nova_compute:
                    raise errors.InvalidData(
                        "The following nova compute instance with target "
                        "'controllers' couldn't be deleted from operational "
                        "environment: nova compute with vSphere cluster name "
                        "'{0}' ".format(vsphere_name),
                        log_message=True
                    )
                for attr, db_value in six.iteritems(db_nova_compute):
                    input_value = input_nova_compute.get(attr)
                    if attr == 'target_node':
                        db_value = cls._get_target_node_id(db_nova_compute)
                        input_value = cls._get_target_node_id(
                            input_nova_compute)
                    if db_value != input_value:
                        raise errors.InvalidData(
                            "Parameter '{0}' of nova compute instance with "
                            "vSphere cluster name '{1}' couldn't be changed".
                            format(attr, vsphere_name),
                            log_message=True
                        )
                db_clusters_names.add(vsphere_name)

        input_clusters_names = set(input_computes_by_vsphere_name.keys())
        if input_clusters_names - db_clusters_names:
            raise errors.InvalidData(
                "Nova compute instances with target 'controllers' couldn't be "
                "added to operational environment. Check nova compute "
                "instances with the following vSphere cluster names: {0}".
                format(', '.join(
                    sorted(input_clusters_names - db_clusters_names))),
                log_message=True
            )

    @classmethod
    def validate(cls, data, instance):
        d = cls.validate_json(data)
        if 'metadata' in d.get('editable'):
            db_metadata = instance.editable.get('metadata')
            input_metadata = d.get('editable').get('metadata')
            if db_metadata != input_metadata:
                raise errors.InvalidData(
                    'Metadata shouldn\'t change',
                    log_message=True
                )

        if instance.cluster.is_locked:
            cls._validate_updated_attributes(d, instance)
        cls._validate_nova_computes(d, instance)

        # TODO(apopovych): write validation processing from
        # openstack.yaml for vmware
        return d
