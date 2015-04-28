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
import re

from nailgun.api.v1.validators.base import BaseDefferedTaskValidator
from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema import cluster as cluster_schema
from nailgun.api.v1.validators.node import ProvisionSelectedNodesValidator

from nailgun.errors import errors

from nailgun.objects import ClusterCollection
from nailgun.objects import Release


class ClusterValidator(BasicValidator):

    single_schema = cluster_schema.single_schema
    collection_schema = cluster_schema.collection_schema

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
            if not Release.get_by_uid(release_id):
                raise errors.InvalidData(
                    "Invalid release ID", log_message=True)
        pend_release_id = d.get("pending_release_id")
        if pend_release_id:
            pend_release = Release.get_by_uid(pend_release_id,
                                              fail_if_not_found=True)
            if not release_id:
                if not instance:
                    raise errors.InvalidData(
                        "Cannot set pending release when "
                        "there is no current release",
                        log_message=True
                    )
                release_id = instance.release_id
            curr_release = Release.get_by_uid(release_id)

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
            if ClusterCollection.filter_by(None, name=d["name"]).first():
                raise errors.AlreadyExists(
                    "Environment with this name already exists",
                    log_message=True
                )

        return d

    @classmethod
    def validate_update(cls, data, instance):
        d = cls._validate_common(data, instance=instance)

        if "name" in d:
            query = ClusterCollection.filter_by_not(None, id=instance.id)

            if ClusterCollection.filter_by(query, name=d["name"]).first():
                raise errors.AlreadyExists(
                    "Environment with this name already exists",
                    log_message=True
                )

        for k in ("net_provider",):
            if k in d and getattr(instance, k) != d[k]:
                raise errors.InvalidData(
                    u"Changing '{0}' for environment is prohibited".format(k),
                    log_message=True
                )
        return d


class AttributesValidator(BasicValidator):

    TYPE_VALUE = {
        'checkbox': bool,
        'text': basestring,
        'password': basestring,
        'textarea': basestring,
        'radio': [{'data': basestring, 'description': basestring}],
        'custom_repo_configuration': [{
            'name': basestring,
            'priority': int,
            'section': basestring,
            'suite': basestring,
            'type': basestring,
            'uri': basestring,
        }],
    }

    @classmethod
    def validate(cls, data):
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

        # Validate 'editable' attributes
        if 'editable' in d:
            for attrs in d['editable'].values():
                if not isinstance(attrs, dict):
                    continue
                for attr_name, attr in attrs.items():
                    cls.validate_attribute(attr_name, attr)

        return d

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
        cls.TYPE_VALUE mapping. If regex is present, we additionally check
        that the provided string value matches the regexp.

        :param attr:
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
            raise errors.InvalidData('[{}] {}'.format(attr_name, e.message))

        pattern = attr.get('regex', {}).get('source')
        if pattern and not re.match(pattern, attr['value']):
            raise errors.InvalidData(
                '[{}] Regexp pattern "{}" not matched for value ""'.format(
                    attr_name, pattern, attr['value']
                )
            )


class ClusterChangesValidator(BaseDefferedTaskValidator):

    @classmethod
    def validate(cls, cluster):
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
