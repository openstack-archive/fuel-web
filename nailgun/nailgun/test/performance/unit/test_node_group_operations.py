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

import functools

from nailgun import consts
from nailgun.test.base import EnvironmentManager
from nailgun.test.performance import base


class NodeGroupOperationsLoadTest(base.BaseUnitLoadTestCase):

    class NameGenerator(object):

        def __init__(self, base_name):
            self.base_name = base_name
            self.counter = 0

        @property
        def next_name(self):
            self.counter += 1
            return '{0}_{1}'.format(self.base_name, self.counter)

        @property
        def name(self):
            return '{0}_{1}'.format(self.base_name, self.counter)

    @classmethod
    def setUpClass(cls):
        super(NodeGroupOperationsLoadTest, cls).setUpClass()

        cls.env = EnvironmentManager(app=cls.app, session=cls.db)
        cls.env.upload_fixtures(cls.fixtures)
        cls.cluster = cls.env.create_cluster(
            api=False,
            net_provider=consts.CLUSTER_NET_PROVIDERS.neutron,
            net_segment_type=consts.NEUTRON_SEGMENT_TYPES.gre,
        )
        cls.group = cls.env.create_node_group()
        cls.name_gen = cls.NameGenerator('test_nodegroup')
        cls.env.create_nodes(cls.NODES_NUM, cluster_id=cls.cluster['id'])

    @base.evaluate_unit_performance
    def test_node_group_collection_retrieve(self):
        func = functools.partial(
            self.get_handler,
            'NodeGroupCollectionHandler',
        )

        self.check_time_exec(func)

    @base.evaluate_unit_performance
    def test_node_group_collection_creation(self):
        func = functools.partial(
            self.post_handler,
            'NodeGroupCollectionHandler',
            {
                'cluster_id': self.cluster.id,
                'name': self.name_gen.next_name
            }
        )
        self.check_time_exec(func)
