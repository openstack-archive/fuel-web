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

from contextlib import contextmanager

from nailgun import consts
from nailgun.consts import NODE_STATUSES
from nailgun import objects
from nailgun.test import base
from nailgun.db.sqlalchemy.models import Task

class TestMongoRolesAssignment(base.BaseTestCase):

    def test_mongo_assigned_for_pendings_roles(self):
         self.env.create(
            release_kwargs={
                "version": "2014.2-6.0",
                "operating_system": "Ubuntu",
                "attributes_metadata": {
                    "editable": {
                        "additional_components": {
                            "ceilometer": {
                                "value": { ("true") }
                             },
                            "mongo": {
                                "value": { ("true") }
                            },
                        },
                        "external_mongo": {
                            "hosts_ip": {
                                "value": ("0.0.0.0")
                            },
                            "mongo_user": {
                                "value": ("ceilometer")
                            },
                            "mongo_password": {
                                "value": ("ceilometer")
                            },
                            "mongo_db_name": {
                                "value": ("ceilometer")
                            }
                        }
                    }
                }
            },
            cluster_kwargs={'mode': 'ha_compact'},
            nodes_kwargs=[
                {'pending_roles': ['controller'],
                 'status': 'discover',
                 'pending_addition': True}
            ]
         )
         self.cluster = self.env.clusters[0]
         task = Task(name='deploy', cluster=self.cluster)
         self.db.add(task)
         self.db.flush()

         task_obj = objects.Task.get_by_uuid(task.uuid)
         self.assertEquals(consts.TASK_STATUSES.running, task_obj.status)
