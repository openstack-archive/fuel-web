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
        config = OpenstackConfigCollection.filter_by(None, **data).first()
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


class OpenstackConfigCollection(NailgunCollection):

    single = OpenstackConfig

    @classmethod
    def find_configs_for_nodes(cls, cluster, nodes):
        """Returns list of configurations that should be applied.

        Returns list of configurations for specified nodes that will be
        applied. List is sorted by the config_type and node_role fields.
        """
        configs_query = OpenstackConfigCollection.filter_by(
            None, cluster_id=cluster.id, is_active=True)
        configs_query = configs_query.order_by(cls.model.node_role)

        node_ids = set(n.id for n in nodes)
        node_roles = set()

        for node in nodes:
            node_roles.update(node.roles)

        configs = []

        for config in configs_query:
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
