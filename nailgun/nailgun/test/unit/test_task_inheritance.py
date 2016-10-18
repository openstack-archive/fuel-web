# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
#    Licensed under the Apache License, Version 2.0 (the 'License'); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an 'AS IS' BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from nailgun import errors
from nailgun.orchestrator import task_inheritance
from nailgun.test.base import BaseTestCase


class TestTaskInheritance(BaseTestCase):

    processor = task_inheritance.TaskInheritanceProcessor()

    def test_no_parents_linearization(self):
        task = {"id": "parent1"}
        task_id = task["id"]
        tasks_mapping = {task_id: task}
        linearized_tasks = {}
        result = self.processor.linearize(tasks_mapping, linearized_tasks,
                                          task_id)
        self.assertEqual([task["id"]], result)

    def test_one_parent_linearization(self):
        tasks = [
            {"id": "parent1"},
            {"id": "child1", "inherited": ["parent1"]}
        ]
        tasks_mapping = {t["id"]: t for t in tasks}
        linearized_tasks = {}
        result = self.processor.linearize(tasks_mapping, linearized_tasks,
                                          "child1")
        self.assertEqual(["child1", "parent1"], result)

    def test_child_from_child(self):
        tasks = [
            {"id": "parent1"},
            {"id": "child1", "inherited": ["parent1"]},
            {"id": "child2", "inherited": ["child1"]}
        ]
        tasks_mapping = {t["id"]: t for t in tasks}
        linearized_tasks = {}
        result = self.processor.linearize(tasks_mapping, linearized_tasks,
                                          "child2")
        self.assertEqual(["child2", "child1", "parent1"], result)

    def test_no_parent(self):
        tasks = [
            {"id": "child1", "inherited": ["parent1"]}
        ]
        tasks_mapping = {t["id"]: t for t in tasks}
        linearized_tasks = {}
        self.assertRaises(errors.TaskNotFound, self.processor.linearize,
                          tasks_mapping, linearized_tasks, "child1")

    def test_complex_hierarchy(self):
        # Example from C3 linearization description:
        # https://www.python.org/download/releases/2.3/mro/
        tasks = [
            {"id": "o"},
            {"id": "a", "inherited": ["o"]},
            {"id": "b", "inherited": ["o"]},
            {"id": "c", "inherited": ["o"]},
            {"id": "d", "inherited": ["o"]},
            {"id": "e", "inherited": ["o"]},
            {"id": "k1", "inherited": ["a", "b", "c"]},
            {"id": "k2", "inherited": ["d", "b", "e"]},
            {"id": "k3", "inherited": ["d", "a"]},
            {"id": "z", "inherited": ["k1", "k2", "k3"]},
        ]
        expected = ["z", "k1", "k2", "k3", "d", "a", "b", "c", "e", "o"]
        tasks_mapping = {t["id"]: t for t in tasks}
        linearized_tasks = {}
        actual = self.processor.linearize(tasks_mapping, linearized_tasks,
                                          "z")
        self.assertEqual(expected, actual)

    def test_linearization_impossible(self):
        tasks = [
            {"id": "o"},
            {"id": "d", "inherited": ["o"]},
            {"id": "e", "inherited": ["d"]},
            {"id": "c", "inherited": ["d", "e"]}
        ]
        tasks_mapping = {t["id"]: t for t in tasks}
        self.assertRaises(
            errors.LinearizationImpossible, self.processor.linearize,
            tasks_mapping, {}, "c")
