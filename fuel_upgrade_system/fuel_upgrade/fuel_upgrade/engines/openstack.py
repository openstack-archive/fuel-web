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
import io
import logging
import os

import requests
import six

from fuel_upgrade.clients import NailgunClient
from fuel_upgrade.engines.base import UpgradeEngine
from fuel_upgrade import utils


logger = logging.getLogger(__name__)


class OpenStackUpgrader(UpgradeEngine):
    """OpenStack Upgrader.

    The class is designed to do the following tasks:

    * install manifests in the system
    * add new releases to nailgun's database
    * add notification about new releases
    """

    def __init__(self, *args, **kwargs):
        super(OpenStackUpgrader, self).__init__(*args, **kwargs)

        #: a list of releases to install
        self.releases = self._read_releases()
        #: a nailgun object - api wrapper
        self.nailgun = NailgunClient(**self.config.endpoints['nginx_nailgun'])

        self._reset_state()

    def upgrade(self):
        self._reset_state()

        self.install_puppets()
        self.install_releases()
        self.install_versions()

    def rollback(self):
        self.remove_releases()
        self.remove_puppets()
        self.remove_versions()

    def install_puppets(self):
        logger.info('Installing puppet manifests...')

        sources = glob.glob(self.config.openstack['puppets']['src'])
        for source in sources:
            destination = os.path.join(
                self.config.openstack['puppets']['dst'],
                os.path.basename(source))
            utils.copy(source, destination)

    def remove_puppets(self):
        logger.info('Removing puppet manifests...')

        sources = glob.glob(self.config.openstack['puppets']['src'])
        for source in sources:
            destination = os.path.join(
                self.config.openstack['puppets']['dst'],
                os.path.basename(source))
            utils.remove(destination)

    def install_versions(self):
        """Copy openstack release versions
        """
        logger.info('Copy openstack release versions...')
        release_versions_cfg = self.config.openstack['release_versions']
        versions = glob.glob(release_versions_cfg['src'])

        utils.create_dir_if_not_exists(release_versions_cfg['dst'])
        for version_file in versions:
            dst = os.path.join(
                release_versions_cfg['dst'],
                os.path.basename(version_file))
            utils.copy(version_file, dst)

    def remove_versions(self):
        """Copy openstack release versions
        """
        logger.info('Copy openstack release versions...')
        release_versions_cfg = self.config.openstack['release_versions']
        versions = glob.glob(release_versions_cfg['src'])

        for version_file in versions:
            dst = os.path.join(
                release_versions_cfg['dst'],
                os.path.basename(version_file))
            utils.remove(dst)

    def install_releases(self):
        # add only new releases to nailgun and inject paths to
        # base repo if needed
        existing_releases = self.nailgun.get_releases()
        releases = self._get_unique_releases(self.releases, existing_releases)

        # upload unexisting releases
        for release in releases:
            # register new release
            logger.debug('Register a new release: %s (%s)',
                         release['name'],
                         release['version'])
            response = self.nailgun.create_release(release)
            # save release id for futher possible rollback
            self._rollback_ids['release'].append(response['id'])
            self.upload_release_deployment_tasks(response)

            if not release.get('is_deployable', True):
                continue

            # add notification abot successfull releases
            logger.debug('Add notification about new release: %s (%s)',
                         release['name'],
                         release['version'])
            response = self.nailgun.create_notification({
                'topic': 'release',
                'message': 'New release available: {0} ({1})'.format(
                    release['name'],
                    release['version'],
                ),
            })
            # save notification id for futher possible rollback
            self._rollback_ids['notification'].append(response['id'])

    def upload_release_deployment_tasks(self, release):
        """Performs os.walk by puppet src, matches all files with tasks
        of given pattern and uploads this for release.

        :param release: dict representation of release
        """
        tasks = []
        release_puppet_path = os.path.join(
            self.config.openstack['puppets']['dst'], release['version'])

        for file_path in utils.iterfiles_filter(
                release_puppet_path,
                self.config.deployment_tasks_file_pattern):

            tasks.extend(utils.read_from_yaml(file_path))

        self.nailgun.put_deployment_tasks(release, tasks)

    def remove_releases(self):
        """Remove all releases that are created by current session.
        """
        for release_id in reversed(self._rollback_ids['release']):
            try:
                logger.debug('Removing release with ID=%s', release_id)
                self.nailgun.remove_release(release_id)
            except (
                requests.exceptions.HTTPError
            ) as exc:
                logger.exception('%s', six.text_type(exc))

        for notif_id in reversed(self._rollback_ids['notification']):
            try:
                logger.debug('Removing notification with ID=%s', notif_id)
                self.nailgun.remove_notification(notif_id)
            except (
                requests.exceptions.HTTPError
            ) as exc:
                logger.exception('%s', six.text_type(exc))

    def _reset_state(self):
        """Remove rollback IDs from the arrays.
        """
        #: a list of ids that have to be removed in case of rollback
        self._rollback_ids = {
            'release': [],
            'notification': [],
        }

    @classmethod
    def _get_unique_releases(cls, releases, existing_releases):
        """Returns a list of releases that aren't exist yet.

        :param releases: a list of releases to filter
        :param existing_releases: a list of existing releases
        :returns: a list of unique releases
        """
        existing_releases = [
            (r['name'], r['version']) for r in existing_releases
        ]

        unique = lambda r: (r['name'], r['version']) not in existing_releases
        return [r for r in releases if unique(r)]

    def _read_releases(self):
        """Returns a list of releases in a dict representation.
        """
        releases = []

        # read releases from a set of files
        for release_yaml in glob.glob(self.config.openstack['releases']):
            with io.open(release_yaml, 'r', encoding='utf-8') as f:
                releases.extend(utils.load_fixture(f))

        return releases

    @property
    def required_free_space(self):
        spaces = {
            self.config.openstack['puppets']['dst']:
            glob.glob(self.config.openstack['puppets']['src']), }

        for dst, srcs in six.iteritems(spaces):
            size = 0
            for src in srcs:
                size += utils.dir_size(src)
            spaces[dst] = size

        return spaces
