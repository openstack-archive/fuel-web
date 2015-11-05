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

import six

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
        data['config_type'] = cls._get_config_type(data)
        data['is_active'] = True
        config = cls.find_config(**data)
        if config:
            cls.delete(config)
        return super(OpenstackConfig, cls).create(data)

    @classmethod
    def delete(cls, instance):
        """Deletes configuration.

        It is required to track history of previous configurations.
        This why delete operation doesn't remove a record from the database,
        it sets `is_active` property to False.
        """
        instance.is_active = False
        db().flush()

    @classmethod
    def _get_config_type(cls, data):
        if 'node_id' in data:
            return consts.OPENSTACK_CONFIG_TYPES.node
        if 'node_role' in data:
            return consts.OPENSTACK_CONFIG_TYPES.role
        return consts.OPENSTACK_CONFIG_TYPES.cluster

    @classmethod
    def _find_configs_query(cls, filters):
        query = db().query(cls.model)
        for key, value in six.iteritems(filters):
            # TODO(asaprykin): There should be a better way to check
            # presence of column in the model.
            field = getattr(cls.model, key)
            if field:
                query = query.filter(field == value)

        return query

    @classmethod
    def find_config(cls, **filters):
        query = cls._find_configs_query(filters)
        return query.first()

    @classmethod
    def find_configs(cls, **filters):
        query = cls._find_configs_query(filters)
        return query.all()

    @classmethod
    def find_configs_for_nodes(cls, cluster, nodes, **filters):
        all_configs = cls.find_configs(cluster_id=cluster.id, is_active=True)
        node_ids = set(n.id for n in nodes)
        node_roles = set()

        for node in nodes:
            node_roles.update(node.roles)

        configs = []

        for config in all_configs:
            if config.config_type == consts.OPENSTACK_CONFIG_TYPES.cluster:
                configs.append(config)
            elif (config.config_type == consts.OPENSTACK_CONFIG_TYPES.node and
                    config.node_id in node_ids):
                configs.append(config)
            elif (config.config_type ==
                    consts.OPENSTACK_CONFIG_TYPES.role and
                    config.node_role in node_roles):
                configs.append(config)

        return configs
