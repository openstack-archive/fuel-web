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

import copy

from nailgun import errors
from nailgun.orchestrator import task_inheritance
from nailgun.test.base import BaseTestCase


class TestTaskInheritance(BaseTestCase):

    processor = task_inheritance.TaskInheritanceProcessor()

    def test_no_parents_linearization(self):
        task = {"id": "parent1"}
        task_id = task["id"]
        tasks_mapping = {task_id: task}
        result = self.processor.linearize(tasks_mapping, {}, task_id)
        self.assertEqual([task["id"]], result)

    def test_one_parent_linearization(self):
        tasks = [
            {"id": "parent1"},
            {"id": "child1", "inherited": ["parent1"]}
        ]
        tasks_mapping = {t["id"]: t for t in tasks}
        result = self.processor.linearize(tasks_mapping, {}, "child1")
        self.assertEqual(["child1", "parent1"], result)

    def test_tasks_not_modified_on_linearization(self):
        tasks = [
            {"id": "parent1"},
            {"id": "child1", "inherited": ["parent1"]}
        ]
        actual = {t["id"]: t for t in tasks}
        expected = copy.deepcopy(actual)
        result = self.processor.linearize(actual, {}, "child1")
        self.assertEqual(["child1", "parent1"], result)
        self.assertEqual(expected, actual)

    def test_child_from_child(self):
        tasks = [
            {"id": "parent1"},
            {"id": "child1", "inherited": ["parent1"]},
            {"id": "child2", "inherited": ["child1"]}
        ]
        tasks_mapping = {t["id"]: t for t in tasks}
        result = self.processor.linearize(tasks_mapping, {}, "child2")
        self.assertEqual(["child2", "child1", "parent1"], result)

    def test_linearization_cache(self):
        tasks = [
            {"id": "parent1"},
            {"id": "child1", "inherited": ["parent1"]},
            {"id": "child2", "inherited": ["child1"]}
        ]
        tasks_mapping = {t["id"]: t for t in tasks}
        linearized_tasks = {}
        result = self.processor.linearize(
            tasks_mapping, linearized_tasks, "parent1")
        self.assertEqual(["parent1"], result)
        result = self.processor.linearize(
            tasks_mapping, linearized_tasks, "child1")
        self.assertEqual(["child1", "parent1"], result)
        result = self.processor.linearize(
            tasks_mapping, linearized_tasks, "child2")
        self.assertEqual(["child2", "child1", "parent1"], result)

        expected = {
            "child1": ["child1", "parent1"],
            "child2": ["child2", "child1", "parent1"],
            "parent1": ["parent1"]
        }
        self.assertEqual(expected, linearized_tasks)

    def test_no_parent(self):
        tasks = [
            {"id": "child1", "inherited": ["parent1"]}
        ]
        tasks_mapping = {t["id"]: t for t in tasks}
        self.assertRaises(errors.TaskNotFound, self.processor.linearize,
                          tasks_mapping, {}, "child1")

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
        actual = self.processor.linearize(tasks_mapping, {}, "z")
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

    def test_linearization_on_cycle(self):
        tasks = [
            {"id": "o"},
            {"id": "d", "inherited": ["o", "c"]},
            {"id": "e", "inherited": ["d"]},
            {"id": "c", "inherited": ["e"]}
        ]
        tasks_mapping = {t["id"]: t for t in tasks}
        self.assertRaises(
            RuntimeError, self.processor.linearize,
            tasks_mapping, {}, "c")

    def test_process_wrong_hierarchy(self):
        tasks = [
            {"id": "o"},
            {"id": "d", "inherited": ["o"]},
            {"id": "e", "inherited": ["d"]},
            {"id": "c", "inherited": ["d", "e"]}
        ]
        self.assertRaises(errors.WrongTasksHierarchy,
                          self.processor.process, tasks)

    def test_process_different_types(self):
        tasks = [
            {"id": "o", "type": "puppet"},
            {"id": "d", "type": "shell"},
            {"id": "e", "inherited": ["d"], "type": "shell"},
            {"id": "c", "inherited": ["e", "o"]}
        ]
        self.assertRaises(errors.DifferentTasksTypesInheritance,
                          self.processor.process, tasks)

    def test_process(self):
        tasks = [
            {"id": "o", "params1": {"o_k": "o_v"}},
            {"id": "d", "params1": {"d_k": "d_v"}, "params2": ["d_a", "d_b"]},
            {"id": "e", "inherited": ["d", "o"], "params3": {"e_k": "e_v"}},
            {"id": "f", "inherited": ["o", "d"]},
            {"id": "g", "inherited": ["o", "d"], "params1": {"g_k": "g_v"}}
        ]
        self.processor.process(tasks)
        tasks_mapping = {t["id"]: t for t in tasks}

        expected = {"id": "e", "inherited": ["d", "o"],
                    "params1": {"d_k": "d_v"}, "params2": ["d_a", "d_b"],
                    "params3": {"e_k": "e_v"}}
        self.assertEqual(expected, tasks_mapping["e"])

        expected = {"id": "f", "inherited": ["o", "d"],
                    "params1": {"o_k": "o_v"}, "params2": ["d_a", "d_b"]}
        self.assertEqual(expected, tasks_mapping["f"])

        expected = {"id": "g", "inherited": ["o", "d"],
                    "params1": {"g_k": "g_v"}, "params2": ["d_a", "d_b"]}
        self.assertEqual(expected, tasks_mapping["g"])
