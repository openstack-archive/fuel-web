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

import glob
import logging
import os
import time

from copy import deepcopy

import docker
import requests

from fuel_upgrade.engines.base import UpgradeEngine
from fuel_upgrade.health_checker import FuelUpgradeVerify
from fuel_upgrade.supervisor_client import SupervisorClient
from fuel_upgrade.version_file import VersionFile

from fuel_upgrade import errors
from fuel_upgrade import utils

logger = logging.getLogger(__name__)


class DockerUpgrader(UpgradeEngine):
    """Docker management system for upgrades
    """

    def __init__(self, *args, **kwargs):
        super(DockerUpgrader, self).__init__(*args, **kwargs)

        self.working_directory = self.config.working_directory

        utils.create_dir_if_not_exists(self.working_directory)

        self.docker_client = docker.Client(
            base_url=self.config.docker['url'],
            version=self.config.docker['api_version'],
            timeout=self.config.docker['http_timeout'])

        self.new_release_images = self.make_new_release_images_list()
        self.new_release_containers = self.make_new_release_containers_list()
        self.cobbler_config_path = self.config.cobbler_config_path.format(
            working_directory=self.working_directory)
        self.upgrade_verifier = FuelUpgradeVerify(self.config)

        self.from_version = self.config.from_version
        self.supervisor = SupervisorClient(self.config, self.from_version)
        self.version_file = VersionFile(self.config)
        self.version_file.save_current()

    def upgrade(self):
        """Method with upgarde logic
        """
        # Preapre env for upgarde
        self.save_db()
        self.save_cobbler_configs()

        # NOTE(akislitsky): fix for bug
        # https://bugs.launchpad.net/fuel/+bug/1354465
        # supervisord can restart old container even if it already stopped
        # and new container start will be failed. We switch configs
        # before upgrade, so if supervisord will try to start container
        # it will be new container.
        self.switch_to_new_configs()

        # Run upgrade
        self.supervisor.stop_all_services()
        self.stop_fuel_containers()
        self.upload_images()
        self.stop_fuel_containers()
        self.create_containers()
        self.stop_fuel_containers()

        # Update configs and run new services
        self.generate_configs()
        self.version_file.switch_to_new()
        self.supervisor.restart_and_wait()
        self.upgrade_verifier.verify()

    def rollback(self):
        """Method which contains rollback logic
        """
        self.version_file.switch_to_previous()
        self.supervisor.switch_to_previous_configs()
        self.supervisor.stop_all_services()
        self.stop_fuel_containers()
        self.supervisor.restart_and_wait()

    def on_success(self):
        """Remove saved version files for all upgrades

        NOTE(eli): It solves several problems:

        1. user runs upgrade 5.0 -> 5.1 which fails
        upgrade system saves version which we upgrade
        from in file working_dir/5.1/version.yaml.
        Then user runs upgrade 5.0 -> 5.0.1 which
        successfully upgraded. Then user runs again
        upgrade 5.0.1 -> 5.1, but there is saved file
        working_dir/5.1/version.yaml which contains
        5.0 version, and upgrade system thinks that
        it's upgrading from 5.0 version, as result
        it tries to make database dump from wrong
        version of container.

        2. without this hack user can run upgrade
        second time and loose his data, this hack
        prevents this case because before upgrade
        checker will use current version instead
        of saved version to determine version which
        we run upgrade from.
        """
        for version_file in glob.glob(self.config.version_files_mask):
            utils.remove(version_file)

    @property
    def required_free_space(self):
        """Required free space to run upgrade

        * space for docker
        * several megabytes for configs
        * reserve several megabytes for working directory
          where we keep postgresql dump and cobbler configs

        :returns: dict where key is path to directory
                  and value is required free space
        """
        return {
            self.config.docker['dir']: self._calculate_images_size(),
            self.config.supervisor['configs_prefix']: 10,
            self.config.fuel_config_path: 10,
            self.working_directory: 150}

    def _calculate_images_size(self):
        images_list = [i['docker_image'] for i in self.new_release_images]
        return utils.files_size(images_list)

    def save_db(self):
        """Saves postgresql database into the file
        """
        logger.debug(u'Backup database')
        pg_dump_path = os.path.join(self.working_directory, 'pg_dump_all.sql')
        pg_dump_files = utils.VersionedFile(pg_dump_path)
        pg_dump_tmp_path = pg_dump_files.next_file_name()

        try:
            container_name = self.make_container_name(
                'postgres', self.from_version)

            self.exec_cmd_in_container(
                container_name,
                u"su postgres -c 'pg_dumpall --clean' > {0}".format(
                    pg_dump_tmp_path))
        except (errors.ExecutedErrorNonZeroExitCode,
                errors.CannotFindContainerError) as exc:
            utils.remove_if_exists(pg_dump_tmp_path)
            if not utils.file_exists(pg_dump_path):
                raise

            logger.debug(
                u'Failed to make database dump, '
                'will be used dump from previous run: %s', exc)

        valid_dumps = filter(utils.verify_postgres_dump,
                             pg_dump_files.sorted_files())
        if valid_dumps:
            utils.hardlink(valid_dumps[0], pg_dump_path, overwrite=True)
            map(utils.remove_if_exists,
                valid_dumps[self.config.keep_db_backups_count:])
        else:
            raise errors.DatabaseDumpError(
                u'Failed to make database dump, there '
                'are no valid database backup '
                'files, {0}'.format(pg_dump_path))

    def save_cobbler_configs(self):
        """Copy config files from container
        """
        container_name = self.make_container_name(
            'cobbler', self.from_version)

        try:
            utils.exec_cmd('docker cp {0}:{1} {2}'.format(
                container_name,
                self.config.cobbler_container_config_path,
                self.cobbler_config_path))
        except errors.ExecutedErrorNonZeroExitCode:
            utils.rmtree(self.cobbler_config_path)
            raise

        self.verify_cobbler_configs()

    def verify_cobbler_configs(self):
        """Verify that cobbler config directory
        contains valid data
        """
        configs = glob.glob(
            self.config.cobbler_config_files_for_verifier.format(
                cobbler_config_path=self.cobbler_config_path))

        # NOTE(eli): cobbler config directory should
        # contain at least one file (default.json)
        if len(configs) < 1:
            raise errors.WrongCobblerConfigsError(
                u'Cannot find json files in directory {0}'.format(
                    self.cobbler_config_path))

        for config in configs:
            if not utils.check_file_is_valid_json(config):
                raise errors.WrongCobblerConfigsError(
                    u'Invalid json config {0}'.format(config))

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
        self._log_iptables()
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
                port_bindings=container.get('port_bindings'),
                links=links,
                volumes_from=volumes_from,
                binds=container.get('binds'),
                privileged=container.get('privileged', False))

            if container.get('after_container_creation_command'):
                self.run_after_container_creation_command(container)
            self.clean_docker_iptables_rules(container)
        # Save current rules
        utils.safe_exec_cmd('service iptables save')
        self._log_iptables()

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
            '', retries=30, interval=4)

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
            graph[container['id']] = sorted(set(
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

    def _get_docker_container_public_ports(self, containers):
        """Returns public ports

        :param containers: list of dicts with information about
                           containers which have `Ports` list
                           with items where exist `PublicPort`
                           field
        :returns: list of public ports
        """
        container_ports = []
        for container in containers:
            container_ports.extend(container['Ports'])

        return [container_port['PublicPort']
                for container_port in container_ports]

    def clean_docker_iptables_rules(self, container):
        """Sometimes when we run docker stop
        (version dc9c28f/0.10.0) it doesn't clean
        iptables rules, as result when we run new
        container on the same port we have two rules
        with the same port but with different IPs,
        we have to clean this rules to prevent services
        unavailability.

        Example of the problem:
          $ iptables -t nat -S
          ...
          -A DOCKER -p tcp -m tcp --dport 443 -j DNAT \
            --to-destination 172.17.0.7:443
          -A DOCKER -p tcp -m tcp --dport 443 -j DNAT \
            --to-destination 172.17.0.3:443

          -A DOCKER -d 10.108.0.2/32 -p tcp -m tcp --dport \
            8777 -j DNAT --to-destination 172.17.0.10:8777
          -A DOCKER -d 127.0.0.1/32 -p tcp -m tcp --dport \
            8777 -j DNAT --to-destination 172.17.0.11:8777
          -A DOCKER -d 10.108.0.2/32 -p tcp -m tcp --dport \
            8777 -j DNAT --to-destination 172.17.0.11:8777
        """
        utils.safe_exec_cmd('dockerctl post_start_hooks {0}'.format(
            container['id']))

    def _log_iptables(self):
        """Method for additional logging of iptables rules

        NOTE(eli): Sometimes there are problems with
        iptables rules like this
        https://bugs.launchpad.net/fuel/+bug/1349287
        """
        utils.safe_exec_cmd('iptables -t nat -S')
        utils.safe_exec_cmd('iptables -S')
        utils.safe_exec_cmd('cat /etc/sysconfig/iptables.save')

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
            version = self.config.new_version

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
            new_image['docker_image'] = image['docker_image']
            new_image['docker_file'] = image['docker_file']

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
            self.config.new_version)

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
