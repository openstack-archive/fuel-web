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
        interpret = fuyaql.Fyaql(logger)
        return interpret

    def test_changed(self, interpret, old_context, new_context):
        interpret.expected_state = new_context
        interpret.current_state = old_context
        interpret.node_id = '1'
        interpret.get_contexts()
        interpret.update_contexts()
        interpret.create_evaluator()
        assert interpret.evaluate('changed($)')
        assert interpret.evaluate('changed($.roles)') is False

    def test_changed_without_old_context(self, interpret, new_context):
        interpret.expected_state = new_context
        interpret.current_state = {}
        interpret.node_id = '1'
        interpret.get_contexts()
        interpret.update_contexts()
        interpret.create_evaluator()
        assert interpret.evaluate('changed($)')
        assert interpret.evaluate('changed($.roles)')

    def test_internal_show_command(self, interpret, new_context):
        command, value = interpret.parse_command(':show cluster')
        assert command == ':show cluster'
        assert value is None

    def test_internal_use_command(self, interpret, new_context):
        command, value = interpret.parse_command(':use cluster 1')
        assert command == ':use cluster'
        assert value == '1'

    def test_internal_context_commands(self, interpret, new_context):
        command, value = interpret.parse_command(':oldcontext task 5')
        assert command == ':oldcontext task'
        assert value == '5'
        command, value = interpret.parse_command(':newcontext task 10')
        assert command == ':newcontext task'
        assert value == '10'

    def test_unknown_internal_command(self, interpret, new_context):
        result = interpret.run_internal_command(':some unknown command', None)
        assert result is False
