# -*- coding: utf-8 -*-

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

import os

from nailgun import extensions

from . import handlers


class ClusterUpgradeExtension(extensions.BaseExtension):
    name = 'cluster_upgrade'
    version = '0.0.1'
    description = "Cluster Upgrade Extension"

    urls = [
        {'uri': r'/clusters/(?P<cluster_id>\d+)/upgrade/clone/?$',
         'handler': handlers.ClusterUpgradeCloneHandler},
        {'uri': r'/clusters/(?P<cluster_id>\d+)/upgrade/assign/?$',
         'handler': handlers.NodeReassignHandler},
        {'uri': r'/clusters/(?P<cluster_id>\d+)/upgrade/vips/?$',
         'handler': handlers.MoveVIPsHandler},
    ]

    @classmethod
    def alembic_migrations_path(cls):
        return os.path.join(os.path.dirname(__file__),
                            'alembic_migrations', 'migrations')

    @classmethod
    def on_cluster_delete(cls, cluster):
        from .objects import relations

        relations.UpgradeRelationObject.delete_relation(cluster.id)
