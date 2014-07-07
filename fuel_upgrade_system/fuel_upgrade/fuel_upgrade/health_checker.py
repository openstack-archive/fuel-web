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

import abc
import logging
import socket
import xmlrpclib

import requests
import six

from fuel_upgrade import errors
from fuel_upgrade import utils

logger = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class BaseChecker(object):
    """Base class for all checkers

    :param endpoints: dict of endpoints
    """

    def __init__(self, endpoints):
        self.endpoints = endpoints

    @abc.abstractproperty
    def checker_name(self):
        """Name of the checker
        """

    @abc.abstractmethod
    def check(self):
        """Check if server alive."""

    def safe_get(self, url, auth=None, timeout=0.5):
        """Make get request to specified url
        in case of errors returns None and doesn't
        raise exceptions

        :param url: url to service
        :param auth: tuple where first item is username second is password
        :param timeout: connection timeout

        :returns: tuple where first item is dict or None in case of error
                  second item is status code or None in case of error
        """
        try:
            result = requests.get(url, auth=auth, timeout=timeout)
            return result.json(), result.status_code
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout):
            return None, None
        except ValueError:
            return None, result.status_code

    def check_if_port_open(self, ip, port):
        """Checks if port is open

        :param ip: ip address
        :param port: port

        :returns: False if there is no open port
                  True if there is open port
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex((ip, port))
        except socket.timeout:
            return False

        if result == 0:
            return True

        return False

    def get_xmlrpc(self, url):
        """Creates xmlrpc object

        :param url: path to rpc server
        :returns: ServerProxy object
        """
        try:
            server = xmlrpclib.ServerProxy(url)
        except socket.error:
            return None

        return server


class NailgunChecker(BaseChecker):

    @property
    def checker_name(self):
        return 'nailgun'

    def check(self):
        _, code = self.safe_get(
            'http://{host}:{port}/api/v1/version'.format(
                **self.endpoints['nailgun']))

        return code == 200


class OSTFChecker(BaseChecker):

    @property
    def checker_name(self):
        return 'ostf'

    def check(self):
        _, code = self.safe_get('http://{host}:{port}/'.format(
            **self.endpoints['ostf']))

        return code == 200


class RabbitChecker(BaseChecker):

    @property
    def checker_name(self):
        return 'rabbitmq'

    def check(self):
        nodes, status_code = self.safe_get(
            'http://{host}:{port}/api/nodes'.format(
                **self.endpoints['rabbitmq']),
            auth=(self.endpoints['rabbitmq']['user'],
                  self.endpoints['rabbitmq']['password']))

        return nodes and status_code == 200


class CobblerChecker(BaseChecker):

    @property
    def checker_name(self):
        return 'cobbler'

    def check(self):
        server = self.get_xmlrpc('http://{host}:{port}/cobbler_api'.format(
            **self.endpoints['cobbler']))

        if server is None:
            return False

        try:
            profiles = server.get_profiles()
        except (xmlrpclib.Fault, xmlrpclib.ProtocolError, socket.error):
            return False

        # Check that there are bootstrap, ubuntu, centos profiles
        return len(profiles) >= 3


class PostgresChecker(BaseChecker):

    @property
    def checker_name(self):
        return 'postgres'

    def check(self):
        return self.check_if_port_open(
            self.endpoints['postgres']['host'],
            self.endpoints['postgres']['port'])


class RsyncChecker(BaseChecker):

    @property
    def checker_name(self):
        return 'rsync'

    def check(self):
        return self.check_if_port_open(
            self.endpoints['rsync']['host'],
            self.endpoints['rsync']['port'])


class RsyslogChecker(BaseChecker):

    @property
    def checker_name(self):
        return 'rsyslog'

    def check(self):
        return self.check_if_port_open(
            self.endpoints['rsyslog']['host'],
            self.endpoints['rsyslog']['port'])


class MCollectiveChecker(BaseChecker):

    @property
    def checker_name(self):
        return 'mcollective'

    def check(self):
        exchanges, code = self.safe_get(
            'http://{host}:{port}/api/exchanges'.format(
                **self.endpoints['rabbitmq_mcollective']),
            auth=(self.endpoints['rabbitmq_mcollective']['user'],
                  self.endpoints['rabbitmq_mcollective']['password']))

        if code != 200 or not isinstance(exchanges, list):
            return False

        exchanges = filter(lambda e: isinstance(e, dict), exchanges)

        mcollective_broadcast = filter(
            lambda e: e.get('name') == 'mcollective_broadcast', exchanges)
        mcollective_directed = filter(
            lambda e: e.get('name') == 'mcollective_directed', exchanges)

        return mcollective_directed and mcollective_broadcast


class NginxChecker(BaseChecker):

    @property
    def checker_name(self):
        return 'nginx'

    def check(self):
        _, nailgun_code = self.safe_get(
            'http://{host}:{port}/'.format(**self.endpoints['nginx_nailgun']))
        _, nginx_code = self.safe_get(
            'http://{host}:{port}/'.format(**self.endpoints['nginx_repo']))

        return nailgun_code is not None and nginx_code is not None

class KeystoneChecker(BaseChecker):
    @property
    def checker_name(self):
        return 'keystone'

    def check(self):
        keystone = self.check_if_port_open(
            self.endpoints['keystone']['host'],
            self.endpoints['keystone']['port'])
        keystone_admin = self.check_if_port_open(
            self.endpoints['keystone_admin']['host'],
            self.endpoints['keystone_admin']['port'])
        return keystone and keystone_admin


class IntegrationCheckerPostgresqlNailgunNginx(BaseChecker):

    @property
    def checker_name(self):
        return 'integration_postgres_nailgun_nginx'

    def check(self):
        releases, code = self.safe_get(
            'http://{host}:{port}/api/v1/releases'.format(
                **self.endpoints['nginx_nailgun']))

        return code == 200 and releases


class IntegrationCheckerRabbitMQAstuteNailgun(BaseChecker):

    @property
    def checker_name(self):
        return 'integration_rabbitmq_astute_nailgun'

    def check(self):
        exchanges, code = self.safe_get(
            'http://{host}:{port}/api/exchanges'.format(
                **self.endpoints['rabbitmq']),
            auth=(self.endpoints['rabbitmq']['user'],
                  self.endpoints['rabbitmq']['password']))

        if not exchanges:
            return False

        naily = filter(lambda e: e['name'] == 'naily_service', exchanges)
        nailgun = filter(lambda e: e['name'] == 'nailgun', exchanges)

        return naily and nailgun


class FuelUpgradeVerify(object):
    """Verifies that fuel upgrade is succeed

    :param config: config object
    :param checkers: list of classes which implement :class:`BaseChecker`
    """

    def __init__(self, config, checkers=None):
        self.config = config

        # Set default checkers
        if checkers is None:
            check_classes = [
                NailgunChecker,
                OSTFChecker,
                RabbitChecker,
                CobblerChecker,
                PostgresChecker,
                RsyncChecker,
                RsyslogChecker,
                MCollectiveChecker,
                NginxChecker,
                IntegrationCheckerPostgresqlNailgunNginx,
                IntegrationCheckerRabbitMQAstuteNailgun]

            self.checkers = [check_class(config.endpoints)
                             for check_class in check_classes]
        else:
            self.checkers = checkers

        self.expected_services = [
            checker.checker_name for checker in self.checkers]

    def verify(self):
        """Run fuel verification
        """
        try:
            utils.wait_for_true(
                self.check_if_all_services_ready,
                timeout=self.config.checker['timeout'],
                interval=self.config.checker['interval'])
        except errors.TimeoutError:
            raise errors.UpgradeVerificationError(
                'Failed to run services {0}'.format(
                    self._get_non_running_services()))

    def check_if_all_services_ready(self):
        """Checks if all services are ready

        :returns: True if all services are ready
                  False if there are some services which are not ready
        """
        not_running_services = self._get_non_running_services()
        if not_running_services:
            logger.info('Checkers which are still fail %s',
                        not_running_services)

            return False

        return True

    def _get_non_running_services(self):
        """Get list of services which are not running

        :returns: list
        """
        return list(set(self.expected_services) -
                    set(self._get_running_services()))

    def _get_running_services(self):
        """Get list of services which are running

        :returns: list
        """
        running_services = []
        for checker in self.checkers:
            logger.debug('Start %s checker', checker.checker_name)
            if checker.check():
                running_services.append(checker.checker_name)

        return running_services
