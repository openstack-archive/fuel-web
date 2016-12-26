# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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

from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema import extension as extension_schema
from nailgun import errors
from nailgun.extensions import get_all_extensions


class ExtensionValidator(BasicValidator):
    single_scheme = extension_schema.single_schema
    collection_schema = extension_schema.collection_schema

    @classmethod
    def validate(cls, data):
        data = set(super(ExtensionValidator, cls).validate(data))
        all_extensions = set(ext.name for ext in get_all_extensions())

        not_found_extensions = data - all_extensions
        if not_found_extensions:
            raise errors.CannotFindExtension(
                "No such extensions: {0}".format(
                    ", ".join(sorted(not_found_extensions))))

        return list(data)

    @classmethod
    def validate_delete(cls, extension_names, cluster):
        not_found_extensions = extension_names - set(cluster.extensions)
        if not_found_extensions:
            raise errors.CannotFindExtension(
                "No such extensions to disable: {0}".format(
                    ", ".join(sorted(not_found_extensions))))

        return list(extension_names)
