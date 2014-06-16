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

import logging
import os
import time

from copy import deepcopy

import docker
import requests

from fuel_upgrade.checker import FuelUpgradeVerify
from fuel_upgrade.engines.base import UpgradeEngine
from fuel_upgrade import errors
from fuel_upgrade.supervisor_client import SupervisorClient
from fuel_upgrade import utils

logger = logging.getLogger(__name__)


class DockerUpgrader(UpgradeEngine):
    """Docker management system for upgrades
    """

    def __init__(self, *args, **kwargs):
        super(DockerUpgrader, self).__init__(*args, **kwargs)

        self.working_directory = os.path.join(
            self.config.working_directory,
            self.config.new_version['VERSION']['release'])

        utils.create_dir_if_not_exists(self.working_directory)

        self.docker_client = docker.Client(
            base_url=self.config.docker['url'],
            version=self.config.docker['api_version'],
            timeout=self.config.docker['http_timeout'])

        self.supervisor = SupervisorClient(self.config)
        self.new_release_images = self.make_new_release_images_list()
        self.new_release_containers = self.make_new_release_containers_list()
        self.pg_dump_path = os.path.join(
            self.working_directory, 'pg_dump_all.sql')
        self.upgrade_verifier = FuelUpgradeVerify(self.config)

    def upgrade(self):
        """Method with upgarde logic
        """
        self.supervisor.stop_all_services()
        self.stop_fuel_containers()
        self.upload_images()
        self.stop_fuel_containers()
        self.create_containers()
        self.stop_fuel_containers()
        self.clean_iptables_rules()
        self.generate_configs()
        self.switch_to_new_configs()

        # Reload configs and run new services
        self.supervisor.restart_and_wait()
        self.upgrade_verifier.verify()

    def rollback(self):
        """Method which contains rollback logic
        """
        self.supervisor.switch_to_previous_configs()
        self.supervisor.stop_all_services()
        self.stop_fuel_containers()
        self.supervisor.restart_and_wait()

    def clean_iptables_rules(self):
        pass

    def before_upgrade_actions(self):
        """Run before upgrade actions
        """
        self.save_db()

    def save_db(self):
        """Saves postgresql database into the file
        """
        logger.debug(u'Backup database')

        # TODO(eli): Need to rethink this logic
        # 1. we need to skip it, because in case
        #    if postgresql container is not runinng
        #    after rollback, we will not be able to
        #    take db dump
        # 2. we should not keep it because in case of
        #    failed upgrade user can use rollbacked system
        #    during some time, and then he can run the same
        #    upgrade again, in this case user will have
        #    outdated db data
        #
        # What we can do here is to make postgresql dump
        # and keep all dumps with different names. And
        # restore latest dump.
        if self.verify_postgres_dump():
            logger.info('Database backup exists "{0}", '
                        'do nothing'.format(self.pg_dump_path))
            return

        container_name = self.make_container_name(
            'postgres',
            self.config.current_version['VERSION']['release'])

        try:
            self.exec_cmd_in_container(
                container_name,
                u"su postgres -c 'pg_dumpall --clean' > {0}".format(
                    self.pg_dump_path))
        except errors.ExecutedErrorNonZeroExitCode:
            if os.path.exists(self.pg_dump_path):
                logger.info(u'Remove postgresql dump file because '
                            'it failed {0}'.format(self.pg_dump_path))
                os.remove(self.pg_dump_path)
            raise

        if not self.verify_postgres_dump():
            raise errors.DatabaseDumpError(
                u'Failed to make database dump, {0} file is broken'.format(
                    self.pg_dump_path))

    def verify_postgres_dump(self):
        """Checks that postgresql dump is correct
        """
        if not os.path.exists(self.pg_dump_path):
            return False
        patterns = [
            '-- PostgreSQL database cluster dump',
            '-- PostgreSQL database dump',
            '-- PostgreSQL database dump complete',
            '-- PostgreSQL database cluster dump complete']

        return utils.file_contains_lines(self.pg_dump_path, patterns)

    def post_upgrade_actions(self):
        """Post upgrade actions

        * creates new version yaml file
        * and creates symlink to /etc/fuel/version.yaml
        """
        logger.info(u'Run post upgrade actions')
        version_yaml_from_upgrade = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '../version.yaml'))
        base_config_dir = os.path.join(
            self.config.fuel_config_path,
            self.config.new_version['VERSION']['release'])
        new_version_path = '{0}/version.yaml'.format(
            base_config_dir)

        utils.create_dir_if_not_exists(base_config_dir)
        utils.copy(version_yaml_from_upgrade, new_version_path)
        utils.symlink(new_version_path, self.config.current_fuel_version_path)

    def upload_images(self):
        """Uploads images to docker
        """
        logger.info(u'Start image uploading')

        for image in self.new_release_images:
            logger.debug(u'Try to upload docker image {0}'.format(image))

            docker_image = image['docker_image']
            if not os.path.exists(docker_image):
                logger.warn(u'Cannot find docker image "{0}"'.format(
                    docker_image))
                continue
            # NOTE(eli): docker-py binding
            # doesn't have equal call for
            # image importing which equals to
            # `docker load`
            utils.exec_cmd(u'docker load < "{0}"'.format(docker_image))

    def create_containers(self):
        """Create containers in the right order
        """
        logger.info(u'Started containers creation')
        graph = self.build_dependencies_graph(self.new_release_containers)
        logger.debug(u'Built dependencies graph {0}'.format(graph))
        containers_to_creation = utils.topological_sorting(graph)
        logger.debug(u'Resolved creation order {0}'.format(
            containers_to_creation))

        for container_id in containers_to_creation:
            container = self.container_by_id(container_id)
            logger.debug(u'Start container {0}'.format(container))

            links = self.get_container_links(container)

            created_container = self.create_container(
                container['image_name'],
                name=container.get('container_name'),
                volumes=container.get('volumes'),
                ports=container.get('ports'),
                detach=False)

            volumes_from = []
            for container_id in container.get('volumes_from', []):
                volume_container = self.container_by_id(container_id)
                volumes_from.append(volume_container['container_name'])

            self.start_container(
                created_container,
                port_bindings=self.get_port_bindings(container),
                links=links,
                volumes_from=volumes_from,
                binds=self.get_container_binds(container),
                privileged=container.get('privileged', False))

            if container.get('after_container_creation_command'):
                self.run_after_container_creation_command(container)

    def run_after_container_creation_command(self, container):
        """Runs command in container with retries in
        case of error

        :param container: dict with container information
        """
        command = container['after_container_creation_command']

        def execute():
            self.exec_cmd_in_container(container['container_name'], command)

        self.exec_with_retries(
            execute, errors.ExecutedErrorNonZeroExitCode,
            '', retries=10, interval=3)

    def exec_cmd_in_container(self, container_name, cmd):
        """Execute command in running container

        :param name: name of the container, like fuel-core-5.1-nailgun
        """
        db_container_id = self.container_docker_id(container_name)
        # NOTE(eli): we don't use dockerctl shell
        # instead of lxc-attach here because
        # release 5.0 has a bug which doesn't
        # allow us to use quotes in command
        # https://bugs.launchpad.net/fuel/+bug/1324200
        utils.exec_cmd(
            "lxc-attach --name {0} -- {1}".format(
                db_container_id, cmd))

    def get_port_bindings(self, container):
        """Docker binding accepts port_bindings
        as tuple, here we convert from list to tuple.

        FIXME(eli): https://github.com/dotcloud/docker-py/blob/
                    030516eb290ddbd33429e0a111a07b43480ea6e5/
                    docker/utils/utils.py#L87
        """
        port_bindings = container.get('port_bindings')
        if port_bindings is None:
            return None

        return dict([(k, tuple(v)) for k, v in port_bindings.iteritems()])

    def get_ports(self, container):
        """Docker binding accepts ports as tuple,
        here we convert from list to tuple.

        FIXME(eli): https://github.com/dotcloud/docker-py/blob/
                    73434476b32136b136e1cdb0913fd123126f2a52/
                    docker/client.py#L111-L114
        """
        ports = container.get('ports')
        if ports is None:
            return

        return [port if not isinstance(port, list) else tuple(port)
                for port in ports]

    def exec_with_retries(
            self, func, exceptions, message, retries=0, interval=0):
        # TODO(eli): refactor it and make retries
        # as a decorator

        intervals = retries * [interval]

        for interval in intervals:
            try:
                return func()
            except exceptions as exc:
                if str(exc).endswith(message):
                    time.sleep(interval)
                    continue
                raise

        return func()

    def get_container_links(self, container):
        links = []
        if container.get('links'):
            for container_link in container.get('links'):
                link_container = self.container_by_id(
                    container_link['id'])
                links.append((
                    link_container['container_name'],
                    container_link['alias']))

        return links

    def get_container_binds(self, container):
        """For some bindings we have to pass non hardcoded directory
        as a parameter, e.g. `working_directory` which consists of
        base path and version.
        """
        binds = container.get('binds')
        if binds:
            rendered_binds = {}
            for index, bind in binds.items():
                rendered_binds[index.format(
                    working_directory=self.working_directory)] = bind

            return rendered_binds

        return binds

    @classmethod
    def build_dependencies_graph(cls, containers):
        """Builds graph which based on
        `volumes_from` and `link` parameters
        of container.

        :returns: dict where keys are nodes and
                  values are lists of dependencies
        """
        graph = {}
        for container in containers:
            graph[container['id']] = list(set(
                container.get('volumes_from', []) +
                [link['id'] for link in container.get('links', [])]))

        return graph

    def generate_configs(self):
        """Generates supervisor configs
        and saves them to configs directory
        """
        configs = []

        for container in self.new_release_containers:
            params = {
                'service_name': container['id'],
                'command': u'docker start -a {0}'.format(
                    container['container_name'])
            }
            if container['supervisor_config']:
                configs.append(params)

        self.supervisor.generate_configs(configs)

        cobbler_container = self.container_by_id('cobbler')
        self.supervisor.generate_cobbler_config(
            {'service_name': cobbler_container['id'],
             'container_name': cobbler_container['container_name']})

    def switch_to_new_configs(self):
        """Switches supervisor to new configs
        """
        self.supervisor.switch_to_new_configs()

    def build_images(self):
        """Use docker API to build new containers
        """
        self.remove_new_release_images()

        for image in self.new_release_images:
            logger.info(u'Start image building: {0}'.format(image))
            self.docker_client.build(
                path=image['docker_file'],
                tag=image['name'],
                nocache=True)

            # NOTE(eli): 0.10 and early versions of
            # Docker api dont't return correct http
            # response in case of failed build, here
            # we check if build succed and raise error
            # if it failed i.e. image was not created
            if not self.docker_client.images(name=image):
                raise errors.DockerFailedToBuildImageError(
                    u'Failed to build image {0}'.format(image))

    def volumes_dependencies(self, container):
        """Get list of `volumes` dependencies

        :param contaienr: dict with information about container
        """
        return self.dependencies_names(container, 'volumes_from')

    def link_dependencies(self, container):
        """Get list of `link` dependencies

        :param contaienr: dict with information about container
        """
        return self.dependencies_names(container, 'link')

    def dependencies_names(self, container, key):
        """Returns list of dependencies for specified key

        :param contaienr: dict with information about container
        :param key: key which will be used for dependencies retrieving

        :returns: list of container names
        """
        names = []
        if container.get(key):
            for container_id in container.get(key):
                container = self.container_by_id(container_id)
                names.append(container['container_name'])

        return names

    def stop_fuel_containers(self):
        """Use docker API to shutdown containers
        """
        containers = self.docker_client.containers(limit=-1)
        containers_to_stop = filter(
            lambda c: c['Image'].startswith(self.config.image_prefix),
            containers)

        for container in containers_to_stop:
            logger.debug(u'Stop container: {0}'.format(container))

            self.stop_container(container['Id'])

    def stop_container(self, container_id):
        """Stop docker container

        :param container_id: container id
        """
        logger.debug(u'Stop container: {0}'.format(container_id))

        try:
            self.docker_client.stop(
                container_id, self.config.docker['stop_container_timeout'])
        except requests.exceptions.Timeout:
            # NOTE(eli): docker use SIGTERM signal
            # to stop container if timeout expired
            # docker use SIGKILL to stop container.
            # Here we just want to make sure that
            # container was stopped.
            logger.warn(
                u'Couldn\'t stop ctonainer, try '
                'to stop it again: {0}'.format(container_id))
            self.docker_client.stop(
                container_id, self.config.docker['stop_container_timeout'])

    def run(self, image_name, **kwargs):
        """Run container from image, accepts the
        same parameters as `docker run` command.
        """
        retries = [None]
        retry_interval = kwargs.pop('retry_interval', 0)
        retries_count = kwargs.pop('retries_count', 0)
        if retry_interval and retries_count:
            retries = [retry_interval] * retries_count

        params = deepcopy(kwargs)
        start_command_keys = [
            'lxc_conf', 'port_bindings', 'binds',
            'publish_all_ports', 'links', 'privileged',
            'dns', 'volumes_from']

        start_params = {}
        for start_command_key in start_command_keys:
            start_params[start_command_key] = params.pop(
                start_command_key, None)

        container = self.create_container(image_name, **params)
        self.start_container(container, **start_params)

        if not params.get('detach'):
            for interval in retries:
                logs = self.docker_client.logs(
                    container['Id'],
                    stream=True,
                    stdout=True,
                    stderr=True)

                for log_line in logs:
                    logger.debug(log_line.rstrip())

                exit_code = self.docker_client.wait(container['Id'])
                if exit_code == 0:
                    break

                if interval is not None:
                    logger.warn(u'Failed to run container "{0}": {1}'.format(
                        container['Id'], start_params))
                    time.sleep(interval)
                    self.docker_client.start(container['Id'], **start_params)
            else:
                if exit_code > 0:
                    raise errors.DockerExecutedErrorNonZeroExitCode(
                        u'Failed to execute migraion command "{0}" '
                        'exit code {1} container id {2}'.format(
                            params.get('command'), exit_code, container['Id']))

        return container

    def start_container(self, container, **params):
        """Start containers

        :param container: container name
        :param params: dict of arguments for container starting
        """
        logger.debug(u'Start container "{0}": {1}'.format(
            container['Id'], params))
        self.docker_client.start(container['Id'], **params)

    def create_container(self, image_name, **params):
        """Create container

        :param image_name: name of image
        :param params: parameters format equals to
                       create_container call of docker
                       client
        """
        # We have to delete container because we cannot
        # have several containers with the same name
        container_name = params.get('name')
        if container_name is not None:
            self._delete_container_if_exist(container_name)

        new_params = deepcopy(params)
        new_params['ports'] = self.get_ports(new_params)

        logger.debug(u'Create container from image {0}: {1}'.format(
            image_name, new_params))

        def func_create():
            return self.docker_client.create_container(
                image_name,
                **new_params)

        return self.exec_with_retries(
            func_create,
            docker.errors.APIError,
            "Can't set cookie",
            retries=3,
            interval=2)

    def make_new_release_containers_list(self):
        """Returns list of dicts with information
        for new containers.
        """
        new_containers = []

        for container in self.config.containers:
            new_container = deepcopy(container)
            new_container['image_name'] = self.make_image_name(
                container['from_image'])
            new_container['container_name'] = self.make_container_name(
                container['id'])
            new_containers.append(new_container)

        return new_containers

    def make_container_name(self, container_id, version=None):
        """Returns container name

        :params container_id: container's id
        :returns: name of the container
        """
        if version is None:
            version = self.config.new_version['VERSION']['release']

        return u'{0}{1}-{2}'.format(
            self.config.container_prefix, version, container_id)

    def make_new_release_images_list(self):
        """Returns list of dicts with information
        for new images.
        """
        new_images = []

        for image in self.config.images:
            new_image = deepcopy(image)
            new_image['name'] = self.make_image_name(image['id'])
            new_image['type'] = image['type']
            new_image['docker_image'] = os.path.join(
                self.update_path,
                image['id'] + '.' + self.config.images_extension)
            new_image['docker_file'] = os.path.join(
                self.update_path, image['id'])

            new_images.append(new_image)

        return new_images

    def make_image_name(self, image_id):
        """Makes full image name

        :param image_id: image id from config file
        :returns: full name
        """
        images = filter(
            lambda i: i['id'] == image_id,
            self.config.images)

        if not images:
            raise errors.CannotFindImageError(
                'Cannot find image with id: {0}'.format(image_id))
        image = images[0]

        self._check_image_type(image['type'])
        if image['type'] == 'base':
            return image['id']

        return u'{0}{1}_{2}'.format(
            self.config.image_prefix,
            image['id'],
            self.config.new_version['VERSION']['release'])

    def _check_image_type(self, image_type):
        """Check if image type is valid
        :param image_type: string, type of image
        :raises UnsupportedImageTypeError:
        """
        if not image_type in ('base', 'fuel'):
            raise errors.UnsupportedImageTypeError(
                'Unsupported umage type: {0}'.format(image_type))

    def container_by_id(self, container_id):
        """Get container from new release by id

        :param container_id: id of container
        """
        filtered_containers = filter(
            lambda c: c['id'] == container_id,
            self.new_release_containers)

        if not filtered_containers:
            raise errors.CannotFindContainerError(
                'Cannot find container with id {0}'.format(container_id))

        return filtered_containers[0]

    def container_docker_id(self, name):
        """Returns running container with specified name

        :param name: name of the container
        :returns: id of the container or None if not found
        :raises CannotFindContainerError:
        """
        containers_with_name = self._get_containers_by_name(name)
        running_containers = filter(
            lambda c: c['Status'].startswith('Up'),
            containers_with_name)

        if not running_containers:
            raise errors.CannotFindContainerError(
                'Cannot find running container with name "{0}"'.format(name))

        return running_containers[0]['Id']

    def remove_new_release_images(self):
        """We need to remove images for current release
        because this script can be run several times
        and we have to delete images before images
        building
        """
        # Don't remove base images because we cannot
        # determine what version they belong to
        images = filter(
            lambda i: i.get('type') == 'fuel',
            self.new_release_images)
        image_names = [c['name'] for c in images]

        for image in image_names:
            self._delete_containers_for_image(image)
            if self.docker_client.images(name=image):
                logger.info(u'Remove image for new version {0}'.format(
                    image))
                self.docker_client.remove_image(image)

    def _delete_container_if_exist(self, container_name):
        """Deletes docker container if it exists

        :param container_name: name of container
        """
        found_containers = self._get_containers_by_name(container_name)

        for container in found_containers:
            self.stop_container(container['Id'])
            logger.debug(u'Delete container {0}'.format(container))

            # TODO(eli): refactor it and make retries
            # as a decorator
            def func_remove():
                self.docker_client.remove_container(container['Id'])

            self.exec_with_retries(
                func_remove,
                docker.errors.APIError,
                'Error running removeDevice',
                retries=3,
                interval=2)

    def _get_containers_by_name(self, container_name):
        return filter(
            lambda c: u'/{0}'.format(container_name) in c['Names'],
            self.docker_client.containers(all=True))

    def _delete_containers_for_image(self, image):
        """Deletes docker containers for specified image

        :param image: name of image
        """
        all_containers = self.docker_client.containers(all=True)

        containers = filter(
            # NOTE(eli): We must use convertation to
            # str because in some cases Image is integer
            lambda c: str(c.get('Image')).startswith(image),
            all_containers)

        for container in containers:
            logger.debug(u'Try to stop container {0} which '
                         'depends on image {1}'.format(container['Id'], image))
            self.docker_client.stop(container['Id'])
            logger.debug(u'Delete container {0} which '
                         'depends on image {1}'.format(container['Id'], image))
            self.docker_client.remove_container(container['Id'])


class DockerInitializer(DockerUpgrader):
    """Initial implementation of docker initializer
    will be used for master node initialization
    """

    def upgrade(self):
        self.upload_images()
        self.stop_fuel_containers()
        self.create_containers()
        self.stop_fuel_containers()
        self.generate_configs()
        self.switch_to_new_configs()

        # Reload configs and run new services
        self.supervisor.restart_and_wait()

    def rollback(self):
        logger.warn(u"DockerInitializer doesn't support rollback")
