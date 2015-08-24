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
            for attr_name, attr in attrs.items():
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


class ClusterChangesValidator(BaseDefferedTaskValidator):

    @classmethod
    def validate(cls, cluster):
        cls.validate_release(cluster=cluster)
        ProvisionSelectedNodesValidator.validate_provision(None, cluster)


class VmwareAttributesValidator(BasicValidator):

    single_schema = cluster_schema.vmware_attributes_schema

    @classmethod
    def validate(cls, data, instance=None):
        d = cls.validate_json(data)
        if 'metadata' in d.get('editable'):
            db_metadata = instance.editable.get('metadata')
            input_metadata = d.get('editable').get('metadata')
            if db_metadata != input_metadata:
                raise errors.InvalidData(
                    'Metadata shouldn\'t change',
                    log_message=True
                )

        # TODO(apopovych): write validation processing from
        # openstack.yaml for vmware
        return d
