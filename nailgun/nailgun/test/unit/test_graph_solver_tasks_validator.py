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


import textwrap

import jsonschema

from nailgun.api.v1.validators import orchestrator_graph
from nailgun.test import base


class TestGraphSolverTasksValidator(base.BaseUnitTest):

    validator = orchestrator_graph.GraphSolverTasksValidator

    def test_task_requires_list(self):
        self.assertNotRaises(
            jsonschema.exceptions.ValidationError,
            self.validator.validate_update,
            textwrap.dedent('''
                [{
                    "id": "netconfig",
                    "type": "puppet",
                    "requires": ["tools"]
                }]
            '''),
            instance=None)

    def test_task_requires_yaql(self):
        self.assertNotRaises(
            jsonschema.exceptions.ValidationError,
            self.validator.validate_update,
            textwrap.dedent('''
                [{
                    "id": "netconfig",
                    "type": "puppet",
                    "requires": {
                        "yaql_exp": "$.do_something()"
                    }
                }]
            '''),
            instance=None)

    def test_task_required_for_list(self):
        self.assertNotRaises(
            jsonschema.exceptions.ValidationError,
            self.validator.validate_update,
            textwrap.dedent('''
                [{
                    "id": "netconfig",
                    "type": "puppet",
                    "required_for": ["tools"]
                }]
            '''),
            instance=None)

    def test_task_required_for_yaql(self):
        self.assertNotRaises(
            jsonschema.exceptions.ValidationError,
            self.validator.validate_update,
            textwrap.dedent('''
                [{
                    "id": "netconfig",
                    "type": "puppet",
                    "required_for": {
                        "yaql_exp": "$.do_something()"
                    }
                }]
            '''),
            instance=None)

    def test_task_cross_depends_list(self):
        self.assertNotRaises(
            jsonschema.exceptions.ValidationError,
            self.validator.validate_update,
            textwrap.dedent('''
                [{
                    "id": "netconfig",
                    "type": "puppet",
                    "cross-depends": [{
                        "name": "something"
                    }]
                }]
            '''),
            instance=None)

    def test_task_cross_depends_yaql(self):
        self.assertNotRaises(
            jsonschema.exceptions.ValidationError,
            self.validator.validate_update,
            textwrap.dedent('''
                [{
                    "id": "netconfig",
                    "type": "puppet",
                    "cross-depends": {
                        "yaql_exp": "$.do_something()"
                    }
                }]
            '''),
            instance=None)

    def test_task_cross_depends_yaql_inside(self):
        self.assertNotRaises(
            jsonschema.exceptions.ValidationError,
            self.validator.validate_update,
            textwrap.dedent('''
                [{
                    "id": "netconfig",
                    "type": "puppet",
                    "cross-depends": [{
                        "name": {
                            "yaql_exp": "$.do_something()"
                        },
                        "role": {
                            "yaql_exp": "$.do_something()"
                        }
                    }]
                }]
            '''),
            instance=None)

    def test_task_cross_depended_by_list(self):
        self.assertNotRaises(
            jsonschema.exceptions.ValidationError,
            self.validator.validate_update,
            textwrap.dedent('''
                [{
                    "id": "netconfig",
                    "type": "puppet",
                    "cross-depended-by": [{
                        "name": "something",
                        "role": "something"
                    }]
                }]
            '''),
            instance=None)

    def test_task_cross_depended_by_yaql(self):
        self.assertNotRaises(
            jsonschema.exceptions.ValidationError,
            self.validator.validate_update,
            textwrap.dedent('''
                [{
                    "id": "netconfig",
                    "type": "puppet",
                    "cross-depended-by": {
                        "yaql_exp": "$.do_something()"
                    }
                }]
            '''),
            instance=None)

    def test_task_cross_depended_by_yaql_inside(self):
        self.assertNotRaises(
            jsonschema.exceptions.ValidationError,
            self.validator.validate_update,
            textwrap.dedent('''
                [{
                    "id": "netconfig",
                    "type": "puppet",
                    "cross-depended-by": [{
                        "name": {
                            "yaql_exp": "$.do_something()"
                        },
                        "role": {
                            "yaql_exp": "$.do_something()"
                        }
                    }]
                }]
            '''),
            instance=None)

    def test_task_strategy_int(self):
        self.assertNotRaises(
            jsonschema.exceptions.ValidationError,
            self.validator.validate_update,
            textwrap.dedent('''
                [{
                    "id": "netconfig",
                    "type": "puppet",
                    "parameters": {
                        "strategy": {
                            "type": "parallel",
                            "amount": 42
                        }
                    }
                }]
            '''),
            instance=None)

    def test_task_strategy_yaql(self):
        self.assertNotRaises(
            jsonschema.exceptions.ValidationError,
            self.validator.validate_update,
            textwrap.dedent('''
                [{
                    "id": "netconfig",
                    "type": "puppet",
                    "parameters": {
                        "strategy": {
                            "type": "parallel",
                            "amount": {
                                "yaql_exp": "$.do_something()"
                            }
                        }
                    }
                }]
            '''),
            instance=None)
