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


import logging
from nailgun.fuyaql import fuyaql
import pytest


class TestFuyaql(object):
    @pytest.fixture
    def old_context(self):
        return {
            '1': {
                'uid': 1,
                'roles': ['primary-controller'],
                'debug': 'true',
                'cinder': {
                    'db_password': '9RkYPCQT9V3LerPsp0qvuzmh',
                    'fixed_key': 'f74ce7f535cb61fc0ee8ba77',
                    'user_password': 'n8BMurmecwUWcH52nbdxqPtz'
                }
            }
        }

    @pytest.fixture
    def new_context(self):
        return {
            '1': {
                'uid': 1,
                'roles': ['primary-controller'],
                'debug': 'false',
                'cinder': {
                    'db_password': '9RkYPCQT9V3LerPsp0qvuzmh',
                    'fixed_key': 'f74ce7f535cb61fc0ee8ba77',
                    'user_password': '62493085e6cfcaa4638ec08'
                }
            }
        }

    @pytest.fixture
    def interpret(self):
        logger = logging.getLogger(__name__)
        interpret = fuyaql.Fuyaql(logger)
        return interpret

    def test_changed(self, interpret, old_context, new_context):
        interpret.expected_state = new_context
        interpret.previous_state = old_context
        interpret.node_id = '1'
        interpret.update_contexts()
        assert interpret.evaluate('changed($)')
        assert interpret.evaluate('changed($.roles)') is False

    def test_changed_without_old_context(self, interpret, new_context):
        interpret.expected_state = new_context
        interpret.previous_state = {}
        interpret.node_id = '1'
        interpret.update_contexts()
        assert interpret.evaluate('changed($)')
        assert interpret.evaluate('changed($.roles)')

    def test_internal_show_command(self, interpret, new_context):
        result = interpret.run_internal_command(':show cluster')
        assert result is True

    def test_internal_use_command(self, interpret, new_context):
        result = interpret.run_internal_command(':use cluster 1')
        assert result is True

    def test_internal_context_commands(self, interpret, new_context):
        result = interpret.run_internal_command(':loadprevious task 5')
        assert result is True
        result = interpret.run_internal_command(':loadcurrent task 10')
        assert result is True

    def test_unknown_internal_command(self, interpret, new_context):
        result = interpret.run_internal_command(':some unknown command')
        assert result is False
