# -*- coding: utf-8 -*-
#    Copyright 2014 Mirantis, Inc.
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

from nailgun.test.performance.base import BaseUnitLoadTestCase
from nailgun.test.performance.base import evaluate_unit_performance

class NodeCollectionOperationsLoadTest(BaseUnitLoadTestCase):

    @classmethod
    def setUpClass(cls):
        super(NodeCollectionOperationsLoadTest, cls).setUpClass()
        cls.env.create_nodes(cls.NODES_NUM, cluster_id=cls.cluster['id'])

    @evaluate_unit_performance
    def test_node_collection_network_interface_controllers_retrieve(self):
        func = functools.partial(
            self.get_handler,
            'NodeCollectionNICsDefaultHandler',
        )

        self.check_time_exec(func, 20)
