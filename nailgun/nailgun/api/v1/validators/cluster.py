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

from distutils import version

import six
import sqlalchemy as sa

from nailgun.api.v1.validators import base
from nailgun.api.v1.validators.json_schema import cluster as cluster_schema
from nailgun.api.v1.validators.node import ProvisionSelectedNodesValidator
from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import Node
from nailgun import errors
from nailgun import objects
from nailgun.plugins.manager import PluginManager
from nailgun.utils.restrictions import ComponentsRestrictions


class ClusterValidator(base.BasicValidator):

    single_schema = cluster_schema.single_schema
    collection_schema = cluster_schema.collection_schema

    _blocked_for_update = (
        'net_provider',
    )

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

        return d

    @classmethod
    def _validate_components(cls, release_id, components_list):
        release = objects.Release.get_by_uid(release_id)
        release_components = objects.Release.get_all_components(release)
        ComponentsRestrictions.validate_components(
            components_list,
            release_components,
            release.required_component_types)

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


class ClusterAttributesValidator(base.BasicAttributesValidator):

    @classmethod
    def validate(cls, data, cluster=None, force=False):
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
        models = None

        if cluster is not None:
            attrs = objects.Cluster.get_updated_editable_attributes(cluster, d)
            cls.validate_provision(cluster, attrs)
            cls.validate_allowed_attributes(cluster, d, force)

            models = objects.Cluster.get_restrictions_models(
                cluster, attrs=attrs.get('editable', {}))

        cls.validate_attributes(attrs.get('editable', {}), models, force=force)

        return d

    @classmethod
    def validate_provision(cls, cluster, attrs):
        # NOTE(agordeev): disable classic provisioning for 7.0 or higher
        if version.StrictVersion(cluster.release.environment_version) >= \
                version.StrictVersion(consts.FUEL_IMAGE_BASED_ONLY):
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

    @classmethod
    def validate_allowed_attributes(cls, cluster, data, force):
        """Validates if attributes are hot pluggable or not.

        :param cluster: A cluster instance
        :type cluster: nailgun.db.sqlalchemy.models.cluster.Cluster
        :param data: Changed attributes of cluster
        :type data: dict
        :param force: Allow forcefully update cluster attributes
        :type force: bool
        :raises: errors.NotAllowed
        """
        # TODO(need to enable restrictions check for cluster attributes[1])
        # [1] https://bugs.launchpad.net/fuel/+bug/1519904
        # Validates only that plugin can be installed on deployed env.

        # If cluster is locked we have to check which attributes
        # we want to change and block an entire operation if there
        # one with always_editable=False.
        if not cluster.is_locked or force:
            return

        editable_cluster = objects.Cluster.get_editable_attributes(
            cluster, all_plugins_versions=True)
        editable_request = data.get('editable', {})

        for attr_name, attr_request in six.iteritems(editable_request):
            attr_cluster = editable_cluster.get(attr_name, {})
            meta_cluster = attr_cluster.get('metadata', {})
            meta_request = attr_request.get('metadata', {})

            if PluginManager.is_plugin_data(attr_cluster):
                if meta_request['enabled']:
                    changed_ids = [meta_request['chosen_id']]
                    if meta_cluster['enabled']:
                        changed_ids.append(meta_cluster['chosen_id'])
                    changed_ids = set(changed_ids)
                elif meta_cluster['enabled']:
                    changed_ids = [meta_cluster['chosen_id']]
                else:
                    continue

                for plugin in meta_cluster['versions']:
                    plugin_id = plugin['metadata']['plugin_id']
                    always_editable = plugin['metadata']\
                        .get('always_editable', False)
                    if plugin_id in changed_ids and not always_editable:
                        raise errors.NotAllowed(
                            "Plugin '{0}' version '{1}' couldn't be changed "
                            "after or during deployment."
                            .format(attr_name,
                                    plugin['metadata']['plugin_version']),
                            log_message=True
                        )

            elif not meta_cluster.get('always_editable', False):
                raise errors.NotAllowed(
                    "Environment attribute '{0}' couldn't be changed "
                    "after or during deployment.".format(attr_name),
                    log_message=True
                )


class ClusterChangesValidator(base.BaseDefferedTaskValidator):

    @classmethod
    def validate(cls, cluster, graph_type=None):
        cls.validate_release(cluster=cluster, graph_type=graph_type)
        ProvisionSelectedNodesValidator.validate_provision(None, cluster)


class ClusterStopDeploymentValidator(base.BaseDefferedTaskValidator):

    @classmethod
    def validate(cls, cluster):
        super(ClusterStopDeploymentValidator, cls).validate(cluster)

        # NOTE(aroma): the check must regard the case when stop deployment
        # is called for cluster that was created before master node upgrade
        # to versions >= 8.0 and so having 'deployed_before' flag absent
        # in their attributes.
        # NOTE(vsharshov): task based deployment (>=9.0) implements
        # safe way to stop deployment action, so we can enable
        # stop deployment for such cluster without restrictions.
        # But it is still need to be disabled for old env < 9.0
        # which was already deployed once[1]
        # [1]: https://bugs.launchpad.net/fuel/+bug/1529691
        generated = cluster.attributes.generated
        if generated.get('deployed_before', {}).get('value') and\
                not objects.Release.is_lcm_supported(cluster.release):
            raise errors.CannotBeStopped('Current deployment process is '
                                         'running on a pre-deployed cluster '
                                         'that does not support LCM.')
