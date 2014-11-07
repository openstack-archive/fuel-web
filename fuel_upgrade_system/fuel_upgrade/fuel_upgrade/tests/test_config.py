from copy import deepcopy
from fuel_upgrade.tests.base import BaseTestCase
from fuel_upgrade.config import Config


class TestConfigHidePasswords(BaseTestCase):
    original_conf = {
        'admin_password': 'r00tme',
        'not_a_pass': 1,
        'nested': {
            'password_here': 'JuYReDm4',
            'nested_again': [
                'apassword!',
                'jcqOyKEf',
                {'login': 'root', 'a_password': '8xMflcaD', 'x': 55.2},
                {
                    'and_again': {
                    'UPPERCASE_PASSWORD': 'VpE8gqKN',
                    'password_as_list': ['it', 'will', 'be', 'changed'],
                    'admin_token': 'Ab8ph9qO'
                    }
                }
            ]
        }
    }

    expected_conf = {
        'admin_password': '******',
        'not_a_pass': 1,
        'nested': {
            'password_here': '******',
            'nested_again': [
                'apassword!',
                'jcqOyKEf',
                {'login': 'root', 'a_password': '******', 'x': 55.2},
                {
                    'and_again': {
                    'UPPERCASE_PASSWORD': '******',
                    'password_as_list': '******',
                    'admin_token': '******'
                    }
                }
            ]
        }
    }

    expected_conf_custom_mask = {
        'admin_password': 'XXX',
        'not_a_pass': 1,
        'nested': {
            'password_here': 'XXX',
            'nested_again': [
                'apassword!',
                'jcqOyKEf',
                {'login': 'root', 'a_password': 'XXX', 'x': 55.2},
                {
                    'and_again': {
                    'UPPERCASE_PASSWORD': 'XXX',
                    'password_as_list': 'XXX',
                    'admin_token': 'XXX'
                    }
                }
            ]
        }
    }

    def setUp(self):
        super(TestConfigHidePasswords, self).setUp()
        self.conf = Config(self.original_conf)

    def test_hide_data(self):
        self.assertEqual(
            self.conf.sanitize(keywords=['password', 'token']),
            self.expected_conf
        )

    def test_original_config_unchanged(self):
        copy_conf = deepcopy(self.conf._config)
        self.conf.sanitize(keywords=['password', 'token'])
        self.assertEqual(self.conf._config, copy_conf)

    def test_custom_mask(self):
        self.assertEqual(
            self.conf.sanitize(keywords=['password', 'token'], mask='XXX'),
            self.expected_conf_custom_mask
        )

    def test_empty_keywords(self):
        self.assertEqual(self.conf._config, self.conf.sanitize())
