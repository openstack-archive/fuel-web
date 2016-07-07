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


from nailgun import consts
from nailgun import objects
from nailgun.test import base


class TestPrimaryTagAssignment(base.BaseTestCase):
    def test_primary_tags_assigned(self):
        cluster = self.env.create(
            release_kwargs={'version': '2014.2-6.0',
                            'operating_system': 'Ubuntu'},
            nodes_kwargs=[
                {'pending_roles': ['controller'],
                 'status': consts.NODE_STATUSES.discover,
                 'pending_addition': True},
                {'pending_roles': ['controller'],
                 'status': consts.NODE_STATUSES.discover,
                 'pending_addition': True}])
        objects.Cluster.set_primary_tags(cluster, cluster.nodes)
        nodes = sorted(cluster.nodes, key=lambda node: node.id)

        self.assertTrue(
            any(t.is_primary for t in nodes[0].tags)
        )
        self.assertTrue(
            'primary-controller' in objects.Node.all_tags(nodes[0])
        )
