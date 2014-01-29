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

from sqlalchemy import not_

from nailgun.api.validators.base import BasicValidator
from nailgun.api.validators.cluster import AttributesValidator
from nailgun.db import db
from nailgun.db.sqlalchemy.models import FencingConfiguration
from nailgun.db.sqlalchemy.models import fencing
from nailgun.errors import errors


class FencingConfigValidator(BasicValidator):

    @classmethod
    def validate_update(cls, data, instance):
        d = cls.validate_json(data)
        if not isinstance(d, dict):
            raise errors.InvalidData('FencingConfigValidator')
        if 'policy' not in d or 'primitive_configuration' not in d:
            raise errors.InvalidData('FencingConfigValidator')
        if not isinstance(d['primitive_configuration'], list):
            raise errors.InvalidData('FencingConfigValidator')

        if d['policy'] == fencing.FENCING_POLICIES.disabled:
            if len(d['primitive_configuration']) != 0:
                raise errors.InvalidData('FencingConfigValidator')
            return d

        if len(d['primitive_configuration']) == 0:
            raise errors.InvalidData('FencingConfigValidator')
        for p in d['primitive_configuration']:
            if not isinstance(p, dict):
                raise errors.InvalidData('FencingConfigValidator')

        return d
