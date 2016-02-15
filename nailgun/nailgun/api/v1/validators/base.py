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
import jsonschema
from jsonschema.exceptions import ValidationError
import six

from oslo_serialization import jsonutils

from nailgun.api.v1.validators.json_schema import base_types
from nailgun.errors import errors
from nailgun import objects
from nailgun.utils import restrictions


class BasicValidator(object):

    single_schema = None
    collection_schema = None

    @classmethod
    def validate_json(cls, data):
        # todo(ikutukov): this method not only validation json but also
        # returning parsed data
        if data:
            try:
                res = jsonutils.loads(data)
            except Exception:
                raise errors.InvalidData(
                    "Invalid json received",
                    log_message=True
                )
        else:
            raise errors.InvalidData(
                "Empty request received",
                log_message=True
            )
        return res

    @classmethod
    def validate_request(cls, req, resource_type,
                         single_schema=None,
                         collection_schema=None):
        json_req = cls.validate_json(req)

        use_schema = {
            "single": single_schema or cls.single_schema,
            "collection": collection_schema or cls.collection_schema
        }.get(resource_type)

        try:
            jsonschema.validate(json_req, use_schema)
        except ValidationError as exc:
            if len(exc.path) > 0:
                raise errors.InvalidData(
                    # NOTE(ikutukov): here was a exc.path.pop(). It was buggy
                    # because JSONSchema error path could contain integers
                    # and joining integers as string is not a good idea in
                    # python. So some schema error messages were not working
                    # properly and give 500 error code except 400.
                    ": ".join([six.text_type(exc.path), exc.message])
                )
            raise errors.InvalidData(exc.message)

    @classmethod
    def validate_response(cls, resp, resource_type,
                          single_schema=None,
                          collection_schema=None):
        pass

    @classmethod
    def validate(cls, data):
        return cls.validate_json(data)

    @classmethod
    def validate_schema(cls, data, schema):
        """Validate a given data with a given schema.

        :param data:   a data to validate represented as a dict
        :param schema: a schema to validate represented as a dict;
                       must be in JSON Schema Draft 4 format.
        """
        try:
            checker = jsonschema.FormatChecker()
            jsonschema.validate(data, schema, format_checker=checker)
        except Exception as exc:
            # We need to cast a given exception to the string since it's the
            # only way to print readable validation error. Unfortunately,
            # jsonschema has no base class for exceptions, so we don't know
            # about internal attributes with error description.
            raise errors.InvalidData(str(exc))

    @classmethod
    def validate_release(cls, data=None, cluster=None):
        """Validate if deployment tasks are present in db

        :param cluster: Cluster instance
        :raises NoDeploymentTasks:
        """
        if (cluster and objects.Release.is_granular_enabled(cluster.release)
                and not objects.Cluster.get_deployment_tasks(cluster)):
            raise errors.NoDeploymentTasks(
                "Deployment tasks not found for '{0}' release in the "
                "database. Please upload them. If you're operating "
                "from Fuel Master node, please check '/etc/puppet' "
                "directory.".format(cluster.release.name))


class BaseDefferedTaskValidator(BasicValidator):

    @classmethod
    def validate(cls, cluster):
        pass


class BasicAttributesValidator(BasicValidator):

    @classmethod
    def validate(cls, data):
        data = cls.validate_json(data)
        if 'attributes' not in data:
            raise errors.InvalidData("There are no attributes key",
                                     log_message=True)

        if not isinstance(data['attributes'], dict):
            raise errors.InvalidData("Attributes should be a dictionary",
                                     log_meassage=True)

        attrs = data['attributes']
        cls.validate_attributes(attrs)

        return attrs

    @classmethod
    def validate_attributes(cls, attrs):
        for attr_name, attr in six.iteritems(attrs):
            cls.validate_attribute(attr_name, attr)

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

        schema = copy.deepcopy(base_types.attribute_schema)
        type_ = attr.get('type')
        if type_:
            value_schema = base_types.attribute_type_schemas.get(type_)
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
