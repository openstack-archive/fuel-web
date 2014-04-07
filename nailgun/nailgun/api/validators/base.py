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
