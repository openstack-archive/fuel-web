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

import httplib
import logging
import os
import socket
import stat
import xmlrpclib

from xmlrpclib import Fault

from fuel_upgrade import utils

logger = logging.getLogger(__name__)


class UnixSocketHTTPConnection(httplib.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.host)


class UnixSocketHTTP(httplib.HTTP):
    _connection_class = UnixSocketHTTPConnection


class UnixSocketTransport(xmlrpclib.Transport, object):
    """Http transport for UNIX socket
    """

    def __init__(self, socket_path):
        """Create object

        :params socket_path: path to the socket
        """
        self.socket_path = socket_path
        super(UnixSocketTransport, self).__init__()

    def make_connection(self, host):
        return UnixSocketHTTP(self.socket_path)


class SupervisorClient(object):
    """RPC Client for supervisor
    """
    templates_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), 'templates'))

    def __init__(self, config, from_version):
        """Create supervisor client

        :param config: config object
        """
        self.config = config
        self.from_version = from_version

        self.supervisor_template_path = os.path.join(
            self.templates_dir, 'supervisor.conf')
        self.supervisor_common_template_path = os.path.join(
            self.templates_dir, 'common.conf')
        self.supervisor_config_dir = self.get_config_path(
            self.config.new_version)
        self.previous_supervisor_config_path = self.get_config_path(
            self.from_version)

        utils.create_dir_if_not_exists(self.supervisor_config_dir)
        self.supervisor = self.get_supervisor()

    def get_config_path(self, version):
        """Creates path to supervisor config with
        specific version

        :param version: version of config
        :returns: path to supervisor config
        """
        return os.path.join(
            self.config.supervisor['configs_prefix'], version)

    def get_supervisor(self):
        """Returns supervisor rpc object
        """
        server = xmlrpclib.Server(
            'http://unused_variable',
            transport=UnixSocketTransport(
                self.config.supervisor['endpoint']))

        return server.supervisor

    def switch_to_new_configs(self):
        """Switch to new version of configs
        for supervisor. Creates symlink on special
        directory.
        """
        current_cfg_path = self.config.supervisor['current_configs_prefix']

        utils.symlink(self.supervisor_config_dir, current_cfg_path)

    def switch_to_previous_configs(self):
        """Switch to previous version of fuel
        """
        current_cfg_path = self.config.supervisor['current_configs_prefix']

        utils.symlink(
            self.previous_supervisor_config_path,
            current_cfg_path)

    def stop_all_services(self):
        """Stops all processes
        """
        logger.info(u'Stop all services')
        self.supervisor.stopAllProcesses()

    def restart_and_wait(self):
        """Restart supervisor and wait untill it will be available
        """
        logger.info(u'Restart supervisor')
        self.supervisor.restart()

        def get_all_processes():
            try:
                return self.supervisor.getAllProcessInfo()
            except (IOError, Fault):
                return False

        all_processes = utils.wait_for_true(
            get_all_processes,
            timeout=self.config.supervisor['restart_timeout'])

        logger.debug(u'List of supervisor processes {0}'.format(
            all_processes))

    def generate_configs(self, services):
        """Generates supervisor configs for services

        :param services: list of dicts where `service_name`
                         and `command` are required fields
        """
        logger.info(
            u'Generate supervisor configs for services {0}'.format(services))

        for service in services:
            self.generate_config(service)

    def generate_config(self, service):
        """Generates config for each service

        :param service: dict where `service_name`
                        and `command` are required fields
        """
        config_path = os.path.join(
            self.supervisor_config_dir,
            '{0}'.format('{0}.conf'.format(service['service_name'])))

        log_path = '/var/log/docker-{0}.log'.format(service['service_name'])

        params = {
            'service_name': service['service_name'],
            'command': service['command'],
            'log_path': log_path}

        utils.render_template_to_file(
            self.supervisor_template_path, config_path, params)

    def generate_cobbler_config(self, container):
        """Generates cobbler config

        :param container: dict `service_name` `container_name`
        """
        container_name = container['container_name']
        script_template_path = os.path.join(
            self.templates_dir, 'cobbler_runner')
        script_path = os.path.join('/usr/bin', container_name)

        utils.render_template_to_file(
            script_template_path,
            script_path,
            {'container_name': container_name})

        self.generate_config({
            'service_name': container['service_name'],
            'command': container_name})

        st = os.stat(script_path)
        os.chmod(script_path, st.st_mode | stat.S_IEXEC)
