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

from nailgun.db.sqlalchemy.models import Task
from nailgun.errors import errors
from nailgun import objects
from nailgun.task.task import CheckBeforeDeploymentTask
from nailgun.test import base


class TestMongoNodes(base.BaseTestCase):

    def setUp(self):
        super(TestMongoNodes, self).setUp()

        self.env.create(
            release_kwargs={'version': '2014.2-6.0',
                            'operating_system': 'Ubuntu',
                            "attributes_metadata": {
                                "editable": {
                                    "additional_components": {
                                        "ceilometer": {"value": "true"},
                                        "mongo": {"value": "true"}}}}},
            cluster_kwargs={'mode': 'multinode'},
            nodes_kwargs=[
                {'pending_roles': ['controller'],
                 'status': 'discover',
                 'pending_addition': True},
                {'pending_roles': ['mongo'],
                 'status': 'discover',
                 'pending_addition': True}
            ]
        )

    def test_check_mongo_nodes(self):
        cluster = self.env.clusters[0]
        nodes = objects.Cluster.get_mongo_nodes(cluster)
        self.assertEqual(len(nodes), 1)

        task = Task(name='deploy', cluster=cluster)
        self.assertRaises(errors.ExtMongoCheckerError,
                          CheckBeforeDeploymentTask._check_mongo_nodes,
                          task)
