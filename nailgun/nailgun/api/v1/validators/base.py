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

from nailgun.errors import errors
from nailgun.openstack.common import jsonutils


class BasicValidator(object):

    schema_module = None

    GET_REQUEST_SCHEMA_NAME = 'GET_REQUEST'
    GET_RESPONSE_SCHEMA_NAME = 'GET_RESPONSE'

    POST_REQUEST_SCHEMA_NAME = 'POST_REQUEST'
    POST_RESPONSE_SCHEMA_NAME = 'POST_RESPONSE'

    PATCH_REQUEST_SCHEMA_NAME = 'PATCH_REQUEST'
    PATCH_RESPONSE_SCHEMA_NAME = 'PATCH_RESPONSE'

    PUT_REQUEST_SCHEMA_NAME = 'PUT_REQUEST'
    PUT_RESPONSE_SCHEMA_NAME = 'PUT_RESPONSE'

    DELETE_REQUEST_SCHEMA_NAME = 'DELETE_REQUEST'
    DELETE_RESPONSE_SCHEMA_NAME = 'DELETE_RESPONSE'

    @classmethod
    def validate_get_request(cls, data):
        schema = getattr(
            cls.schema_module,
            cls.GET_REQUEST_SCHEMA_NAME,
            None
        )
        cls.validate_schema(data, schema)

    @classmethod
    def validate_get_response(cls, data):
        schema = getattr(
            cls.schema_module,
            cls.GET_RESPONSE_SCHEMA_NAME,
            None
        )
        cls.validate_schema(data, schema)

    @classmethod
    def validate_post_request(cls, data):
        schema = getattr(
            cls.schema_module,
            cls.POST_REQUEST_SCHEMA_NAME,
            None
        )
        cls.validate_schema(data, schema)

    @classmethod
    def validate_post_response(cls, data):
        schema = getattr(
            cls.schema_module,
            cls.POST_RESPONSE_SCHEMA_NAME,
            None
        )
        cls.validate_schema(data, schema)

    @classmethod
    def validate_put_request(cls, data):
        schema = getattr(
            cls.schema_module,
            cls.PUT_REQUEST_SCHEMA_NAME,
            None
        )
        cls.validate_schema(data, schema)

    @classmethod
    def validate_put_response(cls, data):
        schema = getattr(
            cls.schema_module,
            cls.PUT_RESPONSE_SCHEMA_NAME,
            None
        )
        cls.validate_schema(data, schema)

    @classmethod
    def validate_patch_request(cls, data):
        schema = getattr(
            cls.schema_module,
            cls.PATCH_REQUEST_SCHEMA_NAME,
            None
        )
        cls.validate_schema(data, schema)

    @classmethod
    def validate_patch_response(cls, data):
        schema = getattr(
            cls.schema_module,
            cls.PATCH_RESPONSE_SCHEMA_NAME,
            None
        )
        cls.validate_schema(data, schema)

    @classmethod
    def validate_delete_request(cls, data):
        schema = getattr(
            cls.schema_module,
            cls.DELETE_REQUEST_SCHEMA_NAME,
            None
        )
        cls.validate_schema(data, schema)

    @classmethod
    def validate_delete_response(cls, data):
        schema = getattr(
            cls.schema_module,
            cls.DELETE_RESPONSE_SCHEMA_NAME,
            None
        )
        cls.validate_schema(data, schema)

    @classmethod
    def load_json(cls, raw_data):
        """Loads json from string
        :param raw_data: string with raw request data
        :return: dict
        """
        if raw_data:
            try:
                res = jsonutils.loads(raw_data)
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
    def validate(cls, data):
        return cls.load_json(data)

    @classmethod
    def validate_schema(cls, data, schema):
        """Validate a given data with a given schema. If schema is
        not defined validation is passed

        :param data:   a data to validate represented as a dict
        :param schema: a schema to validate represented as a dict;
                       must be in JSON Schema Draft 4 format.
        """
        if schema is None:
            return
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
    def validate_update(cls, *args, **kwargs):
        pass
