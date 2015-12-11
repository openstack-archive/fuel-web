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
from nailgun.errors import errors
from nailgun.objects import NailgunCollection
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
            cls.disable(config)
        return super(OpenstackConfig, cls).create(data)

    @classmethod
    def disable(cls, instance):
        """Disables configuration.

        It is required to track history of previous configurations.
        This why disable operation doesn't remove a record from the database,
        it sets `is_active` property to False.
        """
        if not instance.is_active:
            raise errors.CannotUpdate(
                "Configuration '{0}' has been already disabled.".format(
                    instance.id))

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
        """Build query to filter configurations.

        Filters are applied like AND condition.
        """
        query = db().query(cls.model).order_by(cls.model.id.desc())
        for key, value in six.iteritems(filters):
            # TODO(asaprykin): There should be a better way to check
            # presence of column in the model.
            field = getattr(cls.model, key, None)
            if field:
                query = query.filter(field == value)

        return query

    @classmethod
    def find_config(cls, **filters):
        """Returns a single configuration for specified filters.

        Example:
            OpenstackConfig.find_config(cluster_id=10, node_id=12)
        """
        query = cls._find_configs_query(filters)
        return query.first()

    @classmethod
    def find_configs(cls, **filters):
        """Returns list of configurations for specified filters.

        Example:
            OpenstackConfig.find_configs(cluster_id=10, node_id=12)
        """
        return cls._find_configs_query(filters)

    @classmethod
    def find_configs_for_nodes(cls, cluster, nodes):
        """Returns list of configurations that should be applied.

        Returns list of configurations for specified nodes that will be
        applied.
        """
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


class OpenstackConfigCollection(NailgunCollection):

    single = OpenstackConfig
