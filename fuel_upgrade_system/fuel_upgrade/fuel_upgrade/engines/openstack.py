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

import io
import logging
import os

import requests
import six

from fuel_upgrade.engines.base import UpgradeEngine
from fuel_upgrade.nailgun_client import NailgunClient
from fuel_upgrade import utils


logger = logging.getLogger(__name__)


class OpenStackUpgrader(UpgradeEngine):
    """OpenStack Upgrader.

    The class is designed to do the following tasks:

    * install repos in the system
    * install manifests in the system
    * add new releases to nailgun's database
    * add notification about new releases
    """

    def __init__(self, *args, **kwargs):
        super(OpenStackUpgrader, self).__init__(*args, **kwargs)

        #: a dictionary with meta information that could be used to
        #: format some data (paths, for example)
        self._meta = {
            'version': self.config.new_version['VERSION']['release'],
            'master_ip': self.config.astute['ADMIN_NETWORK']['ipaddress'],
        }

        releases_yaml = os.path.join(
            self.update_path,
            self.config.openstack['releases']
        )
        with io.open(releases_yaml, 'r', encoding='utf-8') as f:
            #: an array with releases information
            self.releases = utils.load_fixture(f)

        #: a nailgun object - api wrapper
        self.nailgun = NailgunClient(
            self.config.endpoints['nailgun']['host'],
            self.config.endpoints['nailgun']['port'],
        )

        self._update_conf()
        self._reset_rollback_ids()

    def _update_conf(self):
        """Update some conf data:

        * convert relative paths to absolutes
        * format paths with metadata
        * format releases' orchestration data with metadata
        """
        def fixpath(path):
            if not os.path.isabs(path):
                return os.path.join(self.update_path, path)
            return path

        # fix repos paths
        for os_ in ('centos', 'ubuntu'):
            repo = self.config.openstack['repos'][os_]

            for name in ('src', 'dst'):
                repo[name] = fixpath(repo[name].format(**self._meta))

        # fix puppets paths
        for puppet in ('modules', 'manifests'):
            puppet = self.config.openstack['puppets'][puppet]

            for name in ('src', 'dst'):
                puppet[name] = fixpath(puppet[name].format(**self._meta))

        # bulding valid repo paths
        for release in self.releases:
            data = release['orchestrator_data']

            data['repo_metadata']['nailgun'] = \
                data['repo_metadata']['nailgun'].format(**self._meta)
            data['puppet_manifests_source'] = \
                data['puppet_manifests_source'].format(**self._meta)
            data['puppet_modules_source'] = \
                data['puppet_modules_source'].format(**self._meta)

    def upgrade(self):
        logger.info('Starting upgrading...')

        self.install_repos()
        self.install_puppets()
        self.install_releases()

        logger.info('upgrade is done!')

    def rollback(self):
        logger.info('Starting rollbacking...')

        self.remove_releases()
        self.remove_puppets()
        self.remove_repos()

        logger.info('rollback is done!')

    def install_repos(self):
        logger.info('Installing repositories...')

        for os_ in ('centos', 'ubuntu'):
            utils.copytree(
                self.config.openstack['repos'][os_]['src'],
                self.config.openstack['repos'][os_]['dst'],
            )

    def remove_repos(self):
        logger.info('Removing repositories...')

        for os_ in ('centos', 'ubuntu'):
            utils.rmtree(
                self.config.openstack['repos'][os_]['dst']
            )

    def install_puppets(self):
        logger.info('Installing puppets...')

        for puppet in ('modules', 'manifests'):
            utils.copytree(
                self.config.openstack['puppets'][puppet]['src'],
                self.config.openstack['puppets'][puppet]['dst'],
            )

    def remove_puppets(self):
        logger.info('Removing puppets...')

        for puppet in ('modules', 'manifests'):
            utils.rmtree(
                self.config.openstack['puppets'][puppet]['dst']
            )

    def install_releases(self):
        self._reset_rollback_ids()

        # check releases for existing in nailgun side
        releases = self._get_unique_releases(
            self.releases, self.nailgun.get_releases())

        # upload unexisting releases
        for release in releases:
            # register new release
            logger.debug('Register a new release: %s (%s)',
                         release['name'],
                         release['version'])
            response = self.nailgun.create_release(release)
            # save release id for futher possible rollback
            self._rollback_ids['release'].append(response['id'])

            # add notification abot successfull releases
            logger.debug('Add notification about new release: %s (%s)',
                         release['name'],
                         release['version'])
            response = self.nailgun.create_notification({
                'topic': 'release',
                'message': 'New release avaialble: {0} ({1})'.format(
                    release['name'],
                    release['version'],
                ),
            })
            # save notification id for futher possible rollback
            self._rollback_ids['notification'].append(response['id'])

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
                logger.exception(six.text_type(exc))

        for notif_id in reversed(self._rollback_ids['notification']):
            try:
                logger.debug('Removing notification with ID=%s', notif_id)
                self.nailgun.remove_notification(notif_id)
            except (
                requests.exceptions.HTTPError
            ) as exc:
                logger.exception(six.text_type(exc))

    def before_upgrade_actions(self):
        """Nothing to do for this engine.
        """
        pass

    def post_upgrade_actions(self):
        """Nothing to do for this engine.
        """
        pass

    def _reset_rollback_ids(self):
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
