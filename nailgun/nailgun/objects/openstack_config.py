#    Copyright 2015 Mirantis, Inc.
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

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.objects import NailgunObject
from nailgun.objects.serializers.openstack_config \
    import OpenstackConfigSerializer


class OpenstackConfig(NailgunObject):

    model = models.OpenstackConfig
    serializer = OpenstackConfigSerializer

    @classmethod
    def create(cls, data):
        config_type = consts.OPENSTACK_CONFIG_TYPES.cluster

        if 'node_id' in data:
            config_type = consts.OPENSTACK_CONFIG_TYPES.node
        if 'node_role' in data:
            config_type = consts.OPENSTACK_CONFIG_TYPES.role

        data['config_type'] = config_type

        return super(OpenstackConfig, cls).create(data)

    @classmethod
    def find_configs(cls, conditions):
        query = db().query(cls.model)

        for key in ['cluster_id', 'node_id', 'node_role']:
            if key in conditions:
                query = query.filter_by(**{key: conditions[key]})

        return query.all()
