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

import mock
import six

from nailgun import consts
from nailgun import objects
from nailgun.orchestrator import task_based_deployment
from nailgun.test.base import BaseUnitTest
from nailgun.test.base import BaseTestCase


class TestTaskSerializers(BaseTestCase):
    def setUp(self):
        super(TestTaskSerializers, self).setUp()
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"name": "First",
                 "roles": ["controller"]},
                {"name": "Second",
                 "roles": ["compute"]}
            ]
        )

    def test_serialize(self):
        serialized = task_based_deployment.TasksSerializer.serialize(
            self.env, self.env.nodes,
            objects.Cluster.get_deployment_tasks(self.env.clusters[-1])
        )


class TestNoopSerializer(BaseTestCase):
    def setUp(self):
        super(TestNoopSerializer, self).setUp()
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"name": "First",
                 "roles": ["controller"]},
                {"name": "Second",
                 "roles": ["compute"]}
            ]
        )

    def test_get_uids(self):
        serializer = task_based_deployment.NoopSerializer(
            {"id": "deploy_start", "type": "stage"},
            self.env, self.env.nodes
        )
        self.assertEqual([None], serializer.get_uids())
        serializer.task["groups"] = ["compute"]
        self.assertItemsEqual(
            [n.uid for n in self.env.nodes if "compute" in n.roles],
            serializer.get_uids()
        )

    def test_serialize(self):
        serializer = task_based_deployment.NoopSerializer(
            {"id": "deploy_start", "type": "stage"},
            self.env, self.env.nodes
        )
        tasks = list(serializer.serialize())
        self.assertEqual(1, len(tasks))
        task = tasks[0]

        self.assertEqual(
            {
                'type': consts.ORCHESTRATOR_TASK_TYPES.skipped,
                'uids': [None],
                'fail_on_error': False,
                'skipped': True
            },
            task
        )


class TestDeploymentTaskSerializer(BaseUnitTest):
    def make_task(self, task_id, task_type="puppet", **kwargs):
        task = kwargs
        task["id"] = task_id
        task["type"] = task_type
        return task

    def test_get_stage_serializer(self):
        factory = task_based_deployment.DeployTaskSerializer()
        self.assertIs(
            task_based_deployment.CreateVMsOnCompute,
            factory.get_stage_serializer(
                self.make_task("generate_vms")
            )
        )

        self.assertIs(
            task_based_deployment.NoopSerializer,
            factory.get_stage_serializer(
                self.make_task("post_deployment", "stage")
            )
        )
        self.assertIs(
            task_based_deployment.NoopSerializer,
            factory.get_stage_serializer(
                self.make_task("pre_deployment", "skipped")
            )
        )
        self.assertTrue(
            issubclass(
                factory.get_stage_serializer(
                    self.make_task("upload_repos")
                ),
                task_based_deployment.StandartConfigRolesHook
            )
        )


class TestTaskProcessor(BaseUnitTest):
    def setUp(self):
        self.processor = task_based_deployment.TaskProcessor()

    def test_link_tasks_on_same_node(self):
        previous = {
            "id": "test_task_start",
            "uids": ["1", "2"]
        }
        current = {
            "id": "test_task_end",
            "uids": ["1", "2"]
        }
        self.processor.link_tasks(previous, current)
        self.assertEqual(
            ["test_task_start"],
            current["requires"]
        )
        current["requires"] = ["task2"]
        self.processor.link_tasks(previous, current)
        self.assertEqual(
            ["task2", "test_task_start"],
            current["requires"]
        )

    def test_link_tasks_on_different_nodes(self):
        previous = {
            "id": "test_task_start",
            "uids": ["1"]
        }
        current = {
            "id": "test_task_end",
            "uids": ["1", "2"]
        }
        self.processor.link_tasks(previous, current)
        self.assertItemsEqual(
            (
                {"name": "test_task_start", "node_id": n}
                for n in previous["uids"]
            ),
            current["requires_ex"]
        )
        current["requires_ex"] = [{"name": "test_task_start", "node_id": "0"}]
        self.processor.link_tasks(previous, current)
        self.assertItemsEqual(
            (
                {"name": "test_task_start", "node_id": n}
                for n in ["0"] + previous["uids"]
            ),
            current["requires_ex"]
        )

    def test_patch_task(self):
        origin_task = {"id": "task", "requires": "*", "required_for": "*"}
        serialized = {"type": "puppet"}
        self.processor.patch_task(
            origin_task, "task_start", serialized,
            ["requires", "cross-depends"]
        )

        self.assertEqual(
            {"id": "task_start", "type": "puppet", "requires": "*"},
            serialized
        )
        serialized = {"type": "puppet"}
        self.processor.patch_task(
            origin_task, "task_start", serialized
        )
        self.assertEqual(
            {"id": "task_start", "type": "puppet"},
            serialized
        )

    def test_patch_first_task_in_chain(self):
        origin_task = {
            "id": "task", "requires": [], 'cross-depends': [],
            "required_for": [], 'cross-depended-by': []
        }
        serialized = {"type": "puppet"}
        self.processor.patch_first_task_in_chain(origin_task, serialized)
        self.assertEqual(
            {
                "id": "task_start",
                "type": "puppet",
                "requires": [],
                "cross-depends": []
            },
            serialized
        )

    def test_patch_last_task_in_chain(self):
        origin_task = {
            "id": "task", "requires": [], 'cross-depends': [],
            "required_for": [], 'cross-depended-by': []
        }
        serialized = {"type": "puppet"}
        self.processor.patch_last_task_in_chain(origin_task, serialized)
        self.assertEqual(
            {
                "id": "task_end",
                "type": "puppet",
                "required_for": [],
                'cross-depended-by': []
            },
            serialized
        )

    def test_process_if_no_tasks(self):
        tasks = self.processor.process_tasks({"id": "test"}, iter([]))
        self.assertItemsEqual(
            [],
            tasks
        )

    def test_process_tasks_if_not_chain(self):
        origin_task = {
            "id": "task", "requires": ["a"], 'cross-depends': [{"name": "b"}],
            "required_for": ["c"], 'cross-depended-by': [{"name": "d"}]
        }
        serialized = iter([{"type": "puppet"}])

        tasks = self.processor.process_tasks(origin_task, serialized)
        self.assertItemsEqual(
            [dict(origin_task, type="puppet")],
            tasks
        )
        self.assertEqual("task", self.processor.get_origin("task"))

    def test_process_if_chain(self):
        origin_task = {
            "id": "task", "requires": ["a"], 'cross-depends': [{"name": "b"}],
            "required_for": ["c"], 'cross-depended-by': [{"name": "d"}]
        }
        serialized = iter([
            {"type": "puppet", "uids": [None]},
            {"type": "shell", "uids": [None]},
            {"type": "skipped", "uids": [None]}
        ])

        tasks = self.processor.process_tasks(origin_task, serialized)
        self.assertItemsEqual(
            [
                {
                    "id": "task_start", "type": "puppet", "uids": [None],
                    "requires": ["a"],
                    'cross-depends': [{"name": "b"}],
                },
                {
                    "id": "task#1", "type": "shell", "uids": [None],
                    "requires": ["task_start"],
                },
                {
                    "id": "task_end", "type": "skipped", "uids": [None],
                    "requires": ["task#1"],
                    "required_for": ["c"],
                    'cross-depended-by': [{"name": "d"}],
                },
            ],
            tasks
        )
        self.assertEqual("task", self.processor.get_origin("task_start"))
        self.assertEqual("task", self.processor.get_origin("task#1"))
        self.assertEqual("task", self.processor.get_origin("task_end"))
