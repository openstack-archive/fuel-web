# -*- coding: utf-8 -*-

#    Copyright 2014 Mirantis, Inc.
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
import requests
import socket

from fuel_upgrade.health_checker import BaseChecker
from fuel_upgrade.health_checker import FuelUpgradeVerify
from fuel_upgrade.tests.base import BaseTestCase

from fuel_upgrade import health_checker
from fuel_upgrade import errors


class TestBaseChecker(BaseTestCase):

    def setUp(self):
        class BaseCheckerImplementation(BaseChecker):
            @property
            def checker_name(self):
                return 'base_checker'

            def check(self):
                pass

        self.base_checker = BaseCheckerImplementation(None)

    def make_get_request(
            self, url='http://some_url.html',
            auth=('some_user', 'some_password')):
        result = self.base_checker.safe_get(url, auth=auth)

        return result

    @mock.patch('fuel_upgrade.health_checker.requests.get')
    def test_safe_get_request_succeed(self, requests_get):
        json_resp = {'attr': 'value'}
        result = mock.MagicMock()
        result.json.return_value = json_resp
        result.status_code = 200
        requests_get.return_value = result

        params = {'url': 'http://url', 'auth': ('user', 'password')}

        resp = self.make_get_request(**params)

        requests_get.assert_called_once_with(
            params['url'],
            auth=params['auth'],
            timeout=0.5)

        self.assertEquals(resp['body'], json_resp)
        self.assertEquals(resp['code'], 200)

    @mock.patch('fuel_upgrade.health_checker.requests.get')
    def test_safe_get_exception_raised(self, requests_get):
        exceptions = [
            requests.exceptions.ConnectionError(),
            requests.exceptions.Timeout(),
            requests.exceptions.HTTPError(),
            ValueError(),
            socket.timeout()]

        for exception in exceptions:
            requests_get.side_effect = exception
            resp = self.make_get_request()
            self.assertEquals(resp, None)

    @mock.patch('fuel_upgrade.health_checker.requests.get')
    def test_safe_get_non_json_response(self, requests_get):
        result_txt = 'Text result'
        result = mock.MagicMock()
        result.json.side_effect = ValueError()
        result.status_code = 400
        result.text = result_txt
        requests_get.return_value = result

        resp = self.make_get_request()

        self.assertEquals(resp['body'], result_txt)
        self.assertEquals(resp['code'], 400)

    def mock_socket_obj(self, socket_mock):
        socket_obj = mock.MagicMock()
        socket_mock.return_value = socket_obj

        return socket_obj

    @mock.patch('fuel_upgrade.health_checker.socket.socket')
    def test_check_if_port_open_success(self, socket_mock):
        ip = '127.0.0.1'
        port = 1234

        socket_obj = self.mock_socket_obj(socket_mock)
        socket_obj.connect_ex.return_value = 0
        result = self.base_checker.check_if_port_open(ip, port)

        socket_obj.settimeout.assert_called_once_with(0.5)
        socket_mock.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)
        self.assertEquals(result, True)

    @mock.patch('fuel_upgrade.health_checker.socket.socket')
    def test_check_if_port_open_fail(self, socket_mock):
        socket_obj = self.mock_socket_obj(socket_mock)
        socket_obj.connect_ex.return_value = 1
        result = self.base_checker.check_if_port_open('127.0.0.1', 90)

        self.assertEquals(result, False)

    @mock.patch('fuel_upgrade.health_checker.socket.socket')
    def test_check_if_port_open_timeout_exception(self, socket_mock):
        socket_obj = self.mock_socket_obj(socket_mock)
        socket_obj.connect_ex.side_effect = socket.timeout()
        result = self.base_checker.check_if_port_open('127.0.0.1', 90)

        self.assertEquals(result, False)

    @mock.patch('fuel_upgrade.health_checker.xmlrpclib.ServerProxy')
    def test_get_xmlrpc(self, xmlrpc_mock):
        server_mock = mock.MagicMock()
        xmlrpc_mock.return_value = server_mock
        url = 'http://127.0.0.1'
        result = self.base_checker.get_xmlrpc(url)
        xmlrpc_mock.assert_called_once_with(url)

        self.assertEquals(result, server_mock)

    @mock.patch('fuel_upgrade.health_checker.xmlrpclib.ServerProxy')
    def test_get_xmlrpc_connection_error(self, xmlrpc_mock):
        xmlrpc_mock.side_effect = socket.timeout()
        url = 'http://127.0.0.1'
        result = self.base_checker.get_xmlrpc(url)
        xmlrpc_mock.assert_called_once_with(url)

        self.assertEquals(result, None)


class TestFuelUpgradeVerify(BaseTestCase):

    def setUp(self):
        self.config = {'timeout': 1, 'interval': 2}
        self.mock_config = mock.MagicMock()
        self.mock_config.checker.return_value = self.config

        self.checkers = [mock.MagicMock(checker_name=1),
                         mock.MagicMock(checker_name=2)]

        self.verifier = FuelUpgradeVerify(
            self.mock_config, checkers=self.checkers)

    def checkers_returns(self, return_value):
        for checker in self.checkers:
            checker.check.return_value = return_value # flake8: noqa

    @mock.patch('fuel_upgrade.health_checker.utils.wait_for_true')
    def test_verify(self, wait_for_true_mock):
        self.checkers[0].check.return_value = False

        wait_for_true_mock.side_effect = errors.TimeoutError()

        with self.assertRaisesRegexp(
                errors.UpgradeVerificationError,
                'Failed to run services \[1\]'):

            self.verifier.verify()

    def test_check_if_all_services_ready_returns_true(self):
        self.checkers_returns(True)

        result = self.verifier.check_if_all_services_ready()
        self.assertEquals(result, True)

    def test_check_if_all_services_ready_returns_false(self):
        self.checkers_returns(False)

        result = self.verifier.check_if_all_services_ready()
        self.assertEquals(result, False)


class TestCheckers(BaseTestCase):

    safe_get_sucess = {'body': {'a': 3}, 'code': 200}

    def assert_checker_false(self, checker):
        self.assertFalse(checker(self.fake_config.endpoints).check())

    def assert_checker_true(self, checker):
        self.assertTrue(checker(self.fake_config.endpoints).check())

    @mock.patch('fuel_upgrade.health_checker.BaseChecker.safe_get')
    def test_nailgun_checker_returns_true(self, get_mock):
        get_mock.return_value = self.safe_get_sucess
        self.assert_checker_true(
            health_checker.IntegrationCheckerNginxNailgunChecker)

    @mock.patch('fuel_upgrade.health_checker.BaseChecker.safe_get')
    def test_nailgun_checker_returns_false(self, get_mock):
        get_mock.return_value = None
        self.assert_checker_false(
            health_checker.IntegrationCheckerNginxNailgunChecker)

    @mock.patch('fuel_upgrade.health_checker.BaseChecker.safe_get')
    def test_ostf_checker_returns_true(self, get_mock):
        positive_results = [
            {'body': None, 'code': 401},
            {'body': None, 'code': 200}]
        for result in positive_results:
            get_mock.return_value = result
            self.assert_checker_true(health_checker.OSTFChecker)

    @mock.patch('fuel_upgrade.health_checker.BaseChecker.safe_get')
    def test_ostf_checker_returns_false(self, get_mock):
        get_mock.return_value = {'body': None, 'code': 500}
        self.assert_checker_false(health_checker.OSTFChecker)

    @mock.patch('fuel_upgrade.health_checker.BaseChecker.safe_get')
    def test_rabbit_checker_returns_true(self, get_mock):
        get_mock.return_value = self.safe_get_sucess
        self.assert_checker_true(health_checker.RabbitChecker)

    @mock.patch('fuel_upgrade.health_checker.BaseChecker.safe_get')
    def test_rabbit_checker_returns_false_wrong_code(self, get_mock):
        negative_results = [
            {'body': [1, 2], 'code': 500},
            {'body': [], 'code': 200}]

        for result in negative_results:
            get_mock.return_value = result
            self.assert_checker_false(health_checker.RabbitChecker)

    @mock.patch('fuel_upgrade.health_checker.BaseChecker.get_xmlrpc')
    def test_cobbler_checker_returns_true(self, xmlrpc_mock):
        server_mock = mock.MagicMock()
        xmlrpc_mock.return_value = server_mock
        server_mock.get_profiles.return_value = [1, 2, 3]
        self.assert_checker_true(health_checker.CobblerChecker)

    @mock.patch('fuel_upgrade.health_checker.BaseChecker.get_xmlrpc')
    def test_cobbler_checker_returns_false_profiles_error(self, xmlrpc_mock):
        server_mock = mock.MagicMock()
        xmlrpc_mock.return_value = server_mock
        server_mock.get_profiles.return_value = [1, 2]
        self.assert_checker_false(health_checker.CobblerChecker)

    @mock.patch('fuel_upgrade.health_checker.BaseChecker.get_xmlrpc')
    def test_cobbler_checker_returns_false_exception_error(self, xmlrpc_mock):
        server_mock = mock.MagicMock()
        xmlrpc_mock.return_value = server_mock
        server_mock.get_profiles.side_effect = socket.error()
        self.assert_checker_false(health_checker.CobblerChecker)

    @mock.patch('fuel_upgrade.health_checker.BaseChecker.check_if_port_open')
    def test_socket_checkers_return_true(self, port_checker_mock):
        port_checker_mock.return_value = True

        for socket_checker in [health_checker.PostgresChecker,
                               health_checker.RsyncChecker,
                               health_checker.RsyslogChecker]:
            self.assert_checker_true(socket_checker)

    @mock.patch('fuel_upgrade.health_checker.BaseChecker.check_if_port_open')
    def test_socket_checkers_return_false(self, port_checker_mock):
        port_checker_mock.return_value = False

        for socket_checker in [health_checker.PostgresChecker,
                               health_checker.RsyncChecker,
                               health_checker.RsyslogChecker]:
            self.assert_checker_false(socket_checker)

    @mock.patch('fuel_upgrade.health_checker.BaseChecker.safe_get')
    def test_mcollective_checker_returns_true(self, get_mock):
        result = [{'name': 'mcollective_broadcast'},
                  {'name': 'mcollective_directed'}]
        get_mock.return_value = {'body': result, 'code': 200}
        self.assert_checker_true(health_checker.MCollectiveChecker)

    @mock.patch('fuel_upgrade.health_checker.BaseChecker.safe_get')
    def test_mcollective_checker_returns_false(self, get_mock):
        wrong_results = [
            None,
            {'body': [{'name': 'mcollective_broadcast'},
                      {'name': 'mcollective_directed'}],
             'code': 400},

            {'body': [{'name': 'mcollective_broadcast'}],
             'code': 200},

            {'body': None,
             'code': 200},

            {'body': ['str', None],
             'code': 200}]

        for result in wrong_results:
            get_mock.return_value = result
            self.assert_checker_false(health_checker.MCollectiveChecker)

    @mock.patch('fuel_upgrade.health_checker.BaseChecker.safe_get')
    def test_nginx_checker_returns_true(self, get_mock):
        get_mock.return_value = {'body': None, 'code': 400}
        self.assert_checker_true(health_checker.NginxChecker)

    @mock.patch('fuel_upgrade.health_checker.BaseChecker.safe_get')
    def test_nginx_checker_returns_false(self, get_mock):
        get_mock.return_value = None
        self.assert_checker_false(health_checker.NginxChecker)

    @mock.patch('fuel_upgrade.health_checker.BaseChecker.safe_get')
    def test_keystone_checker_returns_true(self, get_mock):
        get_mock.return_value = {'body': {}, 'code': 200}
        self.assert_checker_true(health_checker.KeystoneChecker)

    @mock.patch('fuel_upgrade.health_checker.BaseChecker.safe_get')
    def test_keystone_checker_returns_false(self, get_mock):
        negative_results = [
            {'body': {}, 'code': 400},
            {'body': None, 'code': None}]

        for result in negative_results:
            get_mock.return_value = result
            self.assert_checker_false(health_checker.KeystoneChecker)

    @mock.patch('fuel_upgrade.health_checker.NailgunClient')
    def test_integration_postgres_nailgun_nginx_returns_true(self, nailgun):
        nailgun.return_value.get_releases.return_value = [1, 2]
        self.assert_checker_true(
            health_checker.IntegrationCheckerPostgresqlNailgunNginx)

    @mock.patch('fuel_upgrade.health_checker.NailgunClient')
    def test_integration_postgres_nailgun_nginx_empty_list(self, nailgun):
        nailgun.return_value.get_releases.return_value = []
        self.assert_checker_false(
            health_checker.IntegrationCheckerPostgresqlNailgunNginx)

    @mock.patch('fuel_upgrade.health_checker.NailgunClient')
    def test_integration_postgres_nailgun_nginx_raises_errors(self, nailgun):
        side_effects = [requests.exceptions.ConnectionError(),
                        requests.exceptions.Timeout(),
                        requests.exceptions.HTTPError(),
                        ValueError()]

        for side_effect in side_effects:
            nailgun.return_value.get_releases.side_effect = side_effect
            self.assert_checker_false(
                health_checker.IntegrationCheckerPostgresqlNailgunNginx)

    @mock.patch('fuel_upgrade.health_checker.BaseChecker.safe_get')
    def test_integration_rabbitmq_astute_nailgun_returns_true(self, get_mock):
        result = {'body': [{'name': 'naily_service'},
                           {'name': 'nailgun'}],
                  'code': 200}
        get_mock.return_value = result

        self.assert_checker_true(
            health_checker.IntegrationCheckerRabbitMQAstuteNailgun)

    @mock.patch('fuel_upgrade.health_checker.BaseChecker.safe_get')
    def test_integration_rabbitmq_astute_nailgun_returns_false(self, get_mock):
        negative_results = [
            None,

            {'body': None,
             'code': 200},

            {'body': [{'name': 'naily_service'}],
             'code': 200},

            {'body': [{'name': 'nailgun'}],
             'code': 200},

            {'body': [{'name': 'nailgun'}, {'name': 'naily_service'}],
             'code': 400},

            {'body': [{}], 'code': 200}]

        for result in negative_results:
            get_mock.return_value = result
            self.assert_checker_false(
                health_checker.IntegrationCheckerRabbitMQAstuteNailgun)

    @mock.patch('fuel_upgrade.health_checker.BaseChecker.make_safe_request')
    def test_nailgun_checker_returns_true(self, make_request_mock):
        make_request_mock.return_value = 200
        self.assert_checker_true(
            health_checker.IntegrationOSTFKeystoneChecker)

    @mock.patch('fuel_upgrade.health_checker.BaseChecker.make_safe_request')
    def test_nailgun_checker_returns_false(self, make_request_mock):
        make_request_mock.return_value = 401
        self.assert_checker_false(
            health_checker.IntegrationOSTFKeystoneChecker)
