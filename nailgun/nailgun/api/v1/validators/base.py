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

import jsonschema
from jsonschema.exceptions import ValidationError
import six

from oslo_serialization import jsonutils

from nailgun.errors import errors
from nailgun import objects


class BasicValidator(object):

    single_schema = None
    collection_schema = None

    @classmethod
    def validate_json(cls, data):
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
