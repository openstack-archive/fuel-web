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

"""
Module with config generation logic

Why python based config?
* in first versions it was yaml based config,
  during some time it became really hard to support
  because in yaml config it's impossible to share
  values between parameters
* also we decided not to use any template language
  because you need to learn yet another sublanguage,
  and it's hard to create variables nesting more than 1
"""

import logging
import yaml

from os.path import exists
from os.path import join

logger = logging.getLogger(__name__)


class Config(object):
    """Config object, allow to call first
    level keys as object attributes.

    :param dict config_dict: config dict
    """

    def __init__(self, config_dict):
        # NOTE(eli): initialize _config
        # with __setattr__ to prevent maximum
        # recursion depth exceeded error
        super(Config, self).__setattr__('_config', config_dict)

    def __getattr__(self, name):
        return self._config[name]

    def __setattr__(self, name, value):
        self._config[name] = value

    def __repr__(self):
        return str(self._config)


def read_yaml_config(path):
    """Reads yaml config

    :param str path: path to config
    :returns: deserialized object
    """
    return yaml.load(open(path, 'r'))


def get_version_from_config(path):
    """Retrieves version from config file

    :param str path: path to config
    """
    return read_yaml_config(path)['VERSION']['release']


def build_config(update_path):
    """Builds config

    :param str update_path: path to upgrade
    :returns: :class:`Config` object
    """
    return Config(config(update_path))


def from_fuel_version(current_version_path, from_version_path):
    """Get version of fuel which user run upgrade from
    """
    # NOTE(eli): If this file exists, then user
    # already ran this upgrade script which was
    # for some reasons interrupted
    if exists(from_version_path):
        from_version = get_version_from_config(from_version_path)
        logger.debug('Retrieve version from {0}, '
                     'version is {1}'.format(from_version_path, from_version))
        return from_version

    return get_version_from_config(current_version_path)


def config(update_path):
    """Generates configuration data for upgrade

    :param str update_path: path to upgrade
    :retuns: huuuge dict with all required
             for ugprade parameters
    """
    fuel_config_path = '/etc/fuel/'

    current_fuel_version_path = '/etc/fuel/version.yaml'
    new_upgrade_version_path = join(update_path, 'config/version.yaml')

    current_version = get_version_from_config(current_fuel_version_path)
    new_version = get_version_from_config(new_upgrade_version_path)
    new_version_path = join(
        '/etc/fuel', new_version, 'version.yaml')

    working_directory = join('/var/lib/fuel_upgrade', new_version)

    from_version_path = join(working_directory, 'version.yaml')
    from_version = from_fuel_version(
        current_fuel_version_path, from_version_path)
    previous_version_path = join('/etc/fuel', from_version, 'version.yaml')

    cobbler_container_config_path = '/var/lib/cobbler/config'
    cobbler_config_path = join(working_directory, 'cobbler_configs')
    cobbler_config_files_for_verifier = join(
        cobbler_config_path, 'config/systems.d/*.json')

    current_fuel_astute_path = '/etc/fuel/astute.yaml'
    astute = read_yaml_config(current_fuel_astute_path)

    supervisor = {
        'configs_prefix': '/etc/supervisord.d/',
        'current_configs_prefix': '/etc/supervisord.d/current',
        'endpoint': '/var/run/supervisor.sock',
        'restart_timeout': 600}

    checker = {
        'timeout': 600,
        'interval': 3}

    endpoints = {
        'nginx_nailgun': {
            'port': 8000,
            'host': '0.0.0.0'},

        'nginx_repo': {
            'port': 8080,
            'host': '0.0.0.0'},

        'nailgun': {
            'port': 8001,
            'host': '127.0.0.1'},

        'ostf': {
            'port': 8777,
            'host': '127.0.0.1'},

        'cobbler': {
            'port': 80,
            'host': '127.0.0.1'},

        'postgres': {
            'port': 5432,
            'host': '127.0.0.1'},

        'rsync': {
            'port': 873,
            'host': '127.0.0.1'},

        'rsyslog': {
            'port': 514,
            'host': '127.0.0.1'},

        'rabbitmq': {
            'user': 'naily',
            'password': 'naily',
            'port': 15672,
            'host': '127.0.0.1'},

        'rabbitmq_mcollective': {
            'port': 15672,
            'host': '127.0.0.1',
            'user': 'mcollective',
            'password': 'marionette'}}

    # Configuration data for docker client
    docker = {
        'url': 'unix://var/run/docker.sock',
        'api_version': '1.10',
        'http_timeout': 160,
        'stop_container_timeout': 10,
        'dir': '/var/lib/docker'}

    # Docker image description section
    image_prefix = 'fuel/'

    # Here are described all images which will
    # be loaded into the docker
    # `id` from id we make path to image files
    # `type`
    #   * fuel - create name of image like fuel-core-5.0-postgres
    #   * base - use name without prefix and postfix
    images = [
        {'id': 'astute',
         'type': 'fuel',
         'docker_image': join(update_path, 'images', 'astute.tar'),
         'docker_file': join(update_path, 'astute')},

        {'id': 'cobbler',
         'type': 'fuel',
         'docker_image': join(update_path, 'images', 'cobbler.tar'),
         'docker_file': join(update_path, 'cobbler')},

        {'id': 'mcollective',
         'type': 'fuel',
         'docker_image': join(update_path, 'images', 'mcollective.tar'),
         'docker_file': join(update_path, 'mcollective')},

        {'id': 'nailgun',
         'type': 'fuel',
         'docker_image': join(update_path, 'images', 'nailgun.tar'),
         'docker_file': join(update_path, 'nailgun')},

        {'id': 'nginx',
         'type': 'fuel',
         'docker_image': join(update_path, 'images', 'nginx.tar'),
         'docker_file': join(update_path, 'nginx')},

        {'id': 'ostf',
         'type': 'fuel',
         'docker_image': join(update_path, 'images', 'ostf.tar'),
         'docker_file': join(update_path, 'ostf')},

        {'id': 'postgres',
         'type': 'fuel',
         'docker_image': join(update_path, 'images', 'postgres.tar'),
         'docker_file': join(update_path, 'postgres')},

        {'id': 'rabbitmq',
         'type': 'fuel',
         'docker_image': join(update_path, 'images', 'rabbitmq.tar'),
         'docker_file': join(update_path, 'rabbitmq')},

        {'id': 'rsync',
         'type': 'fuel',
         'docker_image': join(update_path, 'images', 'rsync.tar'),
         'docker_file': join(update_path, 'rsync')},

        {'id': 'rsyslog',
         'type': 'fuel',
         'docker_image': join(update_path, 'images', 'rsyslog.tar'),
         'docker_file': join(update_path, 'rsyslog')},

        {'id': 'busybox',
         'type': 'base',
         'docker_image': join(update_path, 'images', 'busybox.tar'),
         'docker_file': join(update_path, 'busybox')}]

    # Docker containers description section
    container_prefix = 'fuel-core-'

    containers = [

        {'id': 'nailgun',
         'supervisor_config': True,
         'from_image': 'nailgun',
         'port_bindings': {'8001': ['0.0.0.0', 8001]},
         'ports': [8001],
         'links': [
             {'id': 'postgres', 'alias': 'db'},
             {'id': 'rabbitmq', 'alias': 'rabbitmq'}],
         'volumes': ['/usr/share/nailgun/static'],
         'volumes_from': [
             'volume_logs',
             'volume_repos',
             'volume_ssh_keys',
             'volume_fuel_configs']},

        {'id': 'astute',
         'supervisor_config': True,
         'from_image': 'astute',
         'links': [
             {'id': 'rabbitmq', 'alias': 'rabbitmq'}],
         'volumes_from': [
             'volume_logs',
             'volume_repos',
             'volume_ssh_keys',
             'volume_fuel_configs']},

        {'id': 'cobbler',
         'supervisor_config': True,
         'after_container_creation_command': (
             "bash -c 'cp -rn /tmp/upgrade/cobbler_configs/config/* "
             "/var/lib/cobbler/config/'"),
         'from_image': 'cobbler',
         'privileged': True,
         'port_bindings': {
             '80': ['0.0.0.0', 80],
             '443': ['0.0.0.0', 443],
             '53/udp': ['0.0.0.0', 53],
             '69/udp': ['0.0.0.0', 69]},
         'ports': [
             [53, 'udp'],
             [53, 'tcp'],
             67,
             [69, 'udp'],
             [69, 'tcp'],
             80,
             443],
         'volumes_from': [
             'volume_logs',
             'volume_repos',
             'volume_ssh_keys',
             'volume_fuel_configs',
             'volume_upgrade_directory']},

        {'id': 'mcollective',
         'supervisor_config': True,
         'from_image': 'mcollective',
         'privileged': True,
         'volumes_from': [
             'volume_logs',
             'volume_repos',
             'volume_ssh_keys',
             'volume_fuel_configs',
             'volume_dump']},

        {'id': 'rsync',
         'supervisor_config': True,
         'from_image': 'rsync',
         'port_bindings': {
             '873': ['0.0.0.0', 873]},
         'ports': [873],
         'volumes_from': [
             'volume_logs',
             'volume_repos',
             'volume_fuel_configs',
             'volume_puppet_manifests']},

        {'id': 'rsyslog',
         'supervisor_config': True,
         'from_image': 'rsyslog',
         'port_bindings': {
             '514': ['0.0.0.0', 514],
             '514/udp': ['0.0.0.0', 514]},
         'ports': [[514, 'udp'], 514],
         'volumes_from': [
             'volume_logs',
             'volume_repos',
             'volume_fuel_configs']},

        {'id': 'nginx',
         'supervisor_config': True,
         'from_image': 'nginx',
         'port_bindings': {
             '8000': ['0.0.0.0', 8000],
             '8080': ['0.0.0.0', 8080]},
         'ports': [8000, 8080],
         'links': [
             {'id': 'nailgun', 'alias': 'nailgun'},
             {'id': 'ostf', 'alias': 'ostf'}],
         'volumes_from': [
             'volume_repos',
             'nailgun',
             'volume_logs',
             'volume_repos',
             'volume_fuel_configs',
             'volume_dump']},

        {'id': 'rabbitmq',
         'supervisor_config': True,
         'from_image': 'rabbitmq',
         'port_bindings': {
             '4369': ['0.0.0.0', 4369],
             '5672': ['0.0.0.0', 5672],
             '15672': ['0.0.0.0', 15672],
             '61613': ['0.0.0.0', 61613]},
         'ports': [5672, 4369, 15672, 61613],
         'volumes_from': [
             'volume_logs',
             'volume_repos',
             'volume_fuel_configs']},

        {'id': 'ostf',
         'supervisor_config': True,
         'from_image': 'ostf',
         'port_bindings': {
             '8777': ['0.0.0.0', 8777]},
         'ports': [8777],
         'links': [
             {'id': 'postgres', 'alias': 'db'},
             {'id': 'rabbitmq', 'alias': 'rabbitmq'}],
         'volumes_from': [
             'volume_logs',
             'volume_repos',
             'volume_fuel_configs',
             'volume_ssh_keys']},

        {'id': 'postgres',
         'after_container_creation_command': (
             "su postgres -c ""\"psql -f /tmp/upgrade/pg_dump_all.sql "
             "postgres\""),
         'supervisor_config': True,
         'from_image': 'postgres',
         'port_bindings': {
             '5432': ['0.0.0.0', 5432]},
         'ports': [5432],
         'volumes_from': [
             'volume_logs',
             'volume_repos',
             'volume_fuel_configs',
             'volume_upgrade_directory']},

        {'id': 'volume_repos',
         'supervisor_config': False,
         'from_image': 'busybox',
         'volumes': ['/var/www/nailgun'],
         'binds': {
             '/var/www/nailgun': {
                 'bind': '/var/www/nailgun',
                 'ro': False}}},

        {'id': 'volume_logs',
         'supervisor_config': False,
         'from_image': 'busybox',
         'volumes': ['/var/log'],
         'binds': {
             '/var/log/docker-logs': {
                 'bind': '/var/log',
                 'ro': False}}},

        {'id': 'volume_ssh_keys',
         'supervisor_config': False,
         'from_image': 'busybox',
         'volumes': ['/root/.ssh'],
         'binds': {
             '/root/.ssh': {
                 'bind': '/root/.ssh',
                 'ro': False}}},

        {'id': 'volume_dump',
         'supervisor_config': False,
         'from_image': 'busybox',
         'volumes': ['/dump'],
         'binds': {
             '/dump': {
                 'bind': '/var/www/nailgun/dump',
                 'ro': False}}},

        {'id': 'volume_fuel_configs',
         'supervisor_config': False,
         'from_image': 'busybox',
         'volumes': ['/etc/fuel'],
         'binds': {
             '/etc/fuel': {
                 'bind': '/etc/fuel',
                 'ro': False}}},

        {'id': 'volume_puppet_manifests',
         'supervisor_config': False,
         'from_image': 'busybox',
         'volumes': ['/etc/puppet'],
         'binds': {
             '/etc/puppet': {
                 'bind': '/etc/puppet',
                 'ro': True}}},

        {'id': 'volume_upgrade_directory',
         'supervisor_config': False,
         'from_image': 'busybox',
         'volumes': ['/tmp/upgrade'],
         'binds': {
             # NOTE(eli): Use working directory
             # variable to mount it into the container
             working_directory: {
                 'bind': '/tmp/upgrade',
                 'ro': True}}}]

    # This node contains settings of OpenStack upgrader. So please keep all
    # related settings there. Please keep in mind that all paths are relative
    # to source directory that's passed as a command line argument.
    openstack = {
        'releases': join(update_path, 'config', 'openstack.yaml'),

        'actions': [
            {
                'name': 'copy',
                'from': join(update_path, 'puppet', 'manifests'),
                'to': join('/etc/puppet', new_version, 'manifests'),
            },
            {
                'name': 'copy',
                'from': join(update_path, 'puppet', 'modules'),
                'to': join('/etc/puppet', new_version, 'modules'),
            },
            {
                'name': 'copy',
                'from': join(update_path, 'repos', 'centos'),
                'to': join('/var/www/nailgun', new_version, 'centos'),
            },
            {
                'name': 'copy',
                'from': join(update_path, 'repos/ubuntu'),
                'to': join('/var/www/nailgun', new_version, 'ubuntu'),
            }
        ]}

    # Config for host system upgarde engine
    host_system = {
        'manifest_path': join(
            update_path,
            'puppet/modules/nailgun/examples/host-only.pp'),

        'puppet_modules_path': join(
            update_path,
            'puppet/modules/'),

        'repo_config_path': join(
            '/etc/yum.repos.d',
            '{0}_nailgun.repo'.format(new_version)),

        'repo_path': join(
            update_path,
            'repos/centos/x86_64')}

    # Config for bootstrap upgrade
    bootstrap = {
        'actions': [
            {
                'name': 'move',
                'from': '/var/www/nailgun/bootstrap',
                'to': '/var/www/nailgun/{0}_bootstrap'.format(from_version),
                # Don't overwrite backup files
                'overwrite': False,
                'undo': [
                    {
                        # NOTE(eli): Rollback bootstrap files
                        # with copy, because in 5.0 version
                        # we have volumes linking in container
                        # which doesn't work correctly with symlinks
                        'name': 'copy',
                        'from': '/var/www/nailgun/{0}_bootstrap'.format(
                            from_version),
                        'to': '/var/www/nailgun/bootstrap',
                        'undo': [],
                        'overwrite': True
                    }
                ]
            },
            {
                'name': 'symlink',
                'from': '/var/www/nailgun/{0}_bootstrap'.format(from_version),
                'to': '/var/www/nailgun/bootstrap',
                'undo': []
            },
            {
                'name': 'copy',
                'from': join(update_path, 'bootstrap'),
                'to': '/var/www/nailgun/{0}_bootstrap'.format(new_version),
            },
            {
                'name': 'symlink',
                'from': '/var/www/nailgun/{0}_bootstrap'.format(new_version),
                'to': '/var/www/nailgun/bootstrap',
                'undo': []
            }
        ]}

    return locals()
