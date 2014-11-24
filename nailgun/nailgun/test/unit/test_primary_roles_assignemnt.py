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


from nailgun import objects
from nailgun.test import base


class TestPrimaryRoleAssignment(base.BaseTestCase):

    def test_primary_controller_assignment(self):
        self.env.create(
            cluster_kwargs={'mode': 'ha_compact'},
            release_kwargs={'version': '2014.2-6.0',
                            'operating_system': 'Ubuntu'},
            nodes_kwargs=[
                {'pending_roles': ['controller'],
                 'status': 'discover',
                 'pending_addition': True},
                {'pending_roles': ['controller'],
                 'status': 'discover',
                 'pending_addition': True}])
        cluster = self.env.clusters[0]
        objects.Cluster.set_primary_roles(cluster, cluster.nodes)
