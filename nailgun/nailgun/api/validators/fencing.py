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

from collections import Counter

from nailgun.api.validators.base import BasicValidator
from nailgun.db.sqlalchemy.models import fencing
from nailgun.errors import errors
from nailgun.fixtures.fencing import fencing_metadata


class FencingConfigValidator(BasicValidator):

    @classmethod
    def validate_update(cls, data, instance):
        d = cls.validate_json(data)
        cls.validate_schema(d, fencing_metadata)

        if d['policy'] == fencing.FENCING_POLICIES.disabled:
            if len(d['primitive_configuration']) != 0:
                raise errors.InvalidData(
                    'No primitives must be set when fencing is disabled')
            return d

        if len(d['primitive_configuration']) == 0:
            raise errors.InvalidData(
                'Any of primitives must be set when fencing is enabled')
        pnames = Counter([p['name'] for p in d['primitive_configuration']])
        pduplucates = [k for k, v in pnames if v > 1]
        if pduplucates:
            raise errors.InvalidData(
                'Primitive names must not be repeated')

        return d
