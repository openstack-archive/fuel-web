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
import traceback

from copy import deepcopy

from docker import Client

from fuel_upgrade.config import config
from fuel_upgrade import errors
from fuel_upgrade.utils import exec_cmd
from fuel_upgrade.utils import get_request

logger = logging.getLogger(__name__)


class DockerUpgrader(object):
    """Docker management system for upgrades
    """

    def __init__(self, update_path):
        self.update_path = update_path
        self.working_directory = os.path.join(
            config.working_directory, config.version)

        if not os.path.isdir(self.working_directory):
            os.makedirs(self.working_directory)

        self.docker_client = Client(
            base_url=config.docker['url'],
            version=config.docker['api_version'],
            timeout=config.docker['http_timeout'])

    def upgrade(self):
        self.stop_fuel_containers()
        self.build_images()
        self.run_post_build_actions()
        self.stop_fuel_containers()

    def backup(self):
        """We don't need to backup containers
        because we don't remove current version.
        As result here we run backup of database.
        """
        self.backup_db()

    def backup_db(self):
        """Backup postgresql database
        """
        logger.debug(u'Backup database')
        pg_dump_path = os.path.join(self.working_directory, 'pg_dump_all.sql')
        if os.path.exists(pg_dump_path):
            logger.info('Database backup exists "{0}", '
                        'do nothing'.format(pg_dump_path))
            return

        try:
            exec_cmd("su postgres -c 'pg_dumpall' > {0}".format(pg_dump_path))
        except errors.ExecutedErrorNonZeroExitCode:
            if os.path.exists(pg_dump_path):
                logger.info(u'Remove postgresql dump file because '
                            'it failed {0}'.format(pg_dump_path))
                os.remove(pg_dump_path)
            raise

    def stop_fuel_containers(self):
        """Use docker API to shutdown containers
        """
        containers = self.docker_client.containers(limit=-1)
        containers_to_stop = filter(
            lambda c: c['Image'].startswith(config.container_prefix),
            containers)

        for container in containers_to_stop:
            logger.debug(u'Stop container: {0}'.format(container))
            self.docker_client.stop(
                container['Id'], config.docker['stop_container_timeout'])

    def build_images(self):
        """Use docker API to build new containers
        """
        self._remove_new_release_images()

        for container in self.new_release_containers:
            logger.info(u'Start image building: {0}'.format(container))
            self.docker_client.build(
                path=container['docker_file'],
                tag=container['image_name'],
                nocache=True)

    def run_post_build_actions(self):
        """Run db migration for installed services
        """
        logger.info(u'Run data container')
        data_container = self.container_by_id('data')
        # We have to delete container because we
        # several containers with the same name
        self._delete_container_if_exist(data_container['id'])
        binded_volumes = dict([(v, v) for v in data_container['volumes']])
        data_container = self.run(
            data_container['image_name'],
            name=data_container['id'],
            volumes=data_container['volumes'],
            command=data_container['post_build_command'],
            binds=binded_volumes,
            detach=True)

        logger.info(u'Run postgresql container')
        pg_container = self.container_by_id('postgresql')
        pg_container = self.run(
            pg_container['image_name'],
            volumes_from=data_container['Id'],
            ports=[pg_container['port']],
            port_bindings={pg_container['port']: pg_container['port']},
            detach=True)

        logger.info(u'Run db migration for nailgun')
        nailgun_container = self.container_by_id('nailgun')
        self.run(
            nailgun_container['image_name'],
            command=nailgun_container['post_build_command'],
            retry_interval=2,
            retries_count=3)

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
            'publish_all_ports', 'links', 'privileged']

        start_params = {}
        for start_command_key in start_command_keys:
            start_params[start_command_key] = params.pop(
                start_command_key, None)

        # Create container
        logger.debug(
            u'Create container "{0}": {1}'.format(start_params, params))
        container = self.docker_client.create_container(image_name, **params)

        # Start container
        logger.debug(u'Start container "{0}": {1}'.format(
            container['Id'], start_params))
        self.docker_client.start(container['Id'], **start_params)

        if not params.get('detach'):
            for interval in retries:
                logs = self.docker_client.logs(container['Id'], stream=True)
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

    @property
    def new_release_containers(self):
        """Returns list of dicts with images names
        for new release, fuel/container_name/version
        and paths to Dockerfile.
        """
        new_containers = []

        for container in config.containers:
            new_container = deepcopy(container)
            new_container['image_name'] = '{0}{1}/{2}'.format(
                config.container_prefix, container['id'], config.version)
            new_container['docker_file'] = os.path.join(
                self.update_path, container['id'])
            new_containers.append(new_container)

        return new_containers

    def container_by_id(self, container_id):
        return filter(
            lambda c: c['id'] == container_id,
            self.new_release_containers)[0]

    def remove_new_release_images(self):
        """We need to remove images for current release
        because this script can be run several times
        and we have to delete images before images
        building
        """
        names = [c['image_name'] for c in self.new_release_containers]
        for container in names:
            self._delete_containers_for_image(container)
            if self.docker_client.images(name=container):
                logger.info(u'Remove image for new version {0}'.format(
                    container))
                self.docker_client.remove_image(container)

    def _delete_container_if_exist(self, container_id):
        found_containers = filter(
            lambda c: u'/{0}'.format(container_id) in c['Names'],
            self.docker_client.containers(all=True))

        for container in found_containers:
            logger.debug(u'Delete container {0}'.format(container))
            self.docker_client.remove_container(container['Id'])

    def _delete_containers_for_image(self, image):
        all_containers = self.docker_client.containers(all=True)
        containers = filter(
            # We must use convertation to str because
            # in some cases Image is integer
            lambda c: str(c['Image']).startswith(image),
            all_containers)

        for container in containers:
            logger.debug(u'Delete container {0} which '
                         'depends on image {1}'.format(container['Id'], image))
            self.docker_client.remove_container(container['Id'])


class Upgrade(object):
    """Upgrade logic
    """

    def __init__(self,
                 update_path,
                 upgrade_engine,
                 disable_rollback=False):

        logger.debug(
            u'Create Upgrade object with update path "{0}", '
            'upgrade engine "{1}", '
            'disable rollback is "{2}"'.format(
                update_path,
                upgrade_engine.__class__.__name__,
                disable_rollback))

        self.update_path = update_path
        self.upgrade_engine = upgrade_engine
        self.disable_rollback = disable_rollback

    def run(self):
        self.before_upgrade()

        try:
            self.upgrade()
            self.after_upgrade()
        except Exception as exc:
            logger.error(u'Upgrade failed: {0}'.format(exc))
            logger.error(traceback.format_exc())
            if not self.disable_rollback:
                self.rollback()

    def before_upgrade(self):
        logger.debug('Run before upgrade actions')
        self.check_upgrade_opportunity()
        self.make_backup()

    def upgrade(self):
        logger.debug('Run upgrade')
        self.upgrade_engine.upgrade()

    def after_upgrade(self):
        logger.debug('Run after upgrade actions')
        self.run_services()
        self.check_health()

    def make_backup(self):
        logger.debug('Run system backup')
        self.upgrade_engine.backup()

    def check_upgrade_opportunity(self):
        """Sends request to nailgun
        to make sure that there are no
        running tasks
        """
        logger.info('Check upgrade opportunity')
        nailgun = config.endpoints['nailgun']
        tasks_url = 'http://{0}:{1}/api/v1/tasks'.format(
            nailgun['host'], nailgun['port'])

        tasks = get_request(tasks_url)

        running_tasks = filter(
            lambda t: t['status'] == 'running', tasks)

        if running_tasks:
            tasks_msg = ['id={0} cluster={1} name={2}'.format(
                t.get('id'),
                t.get('cluster'),
                t.get('name')) for t in running_tasks]

            error_msg = 'Cannot run upgrade, tasks are running: {0}'.format(
                ' '.join(tasks_msg))

            raise errors.CannotRunUpgrade(error_msg)

    def run_services(self):
        logger.debug('Run services')

    def check_health(self):
        logger.debug('Check that upgrade passed correctly')

    def rollback(self):
        logger.debug('Run rollback')
        self.upgrade_engine.rollback()
