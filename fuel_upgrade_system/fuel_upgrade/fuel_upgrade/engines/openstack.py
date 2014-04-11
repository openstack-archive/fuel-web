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
import json
import logging
import os

from fuel_upgrade.engines import UpgradeEngine
from fuel_upgrade.nailgun_client import NailgunClient


logger = logging.getLogger(__name__)


class OpenStackUpgrader(UpgradeEngine):
    """OpenStack Upgrader.

    The class is designed to do the following tasks:

    * add new releases to nailgun's database
    * add notification about new releases
    """
    def __init__(self, *args, **kwargs):
        super(OpenStackUpgrader, self).__init__(*args, **kwargs)

        # load information about releases
        releases = os.path.join(
            self.update_path,
            self.config.openstack['releases']
        )

        with io.open(releases, 'r', encoding='utf-8') as f:
            releases = json.loads(f.read())

            # make sure we have an array
            if isinstance(releases, dict):
                releases = [releases]

        #: an array with releases information
        self.releases = releases

        #: a nailgun object - api wrapper
        self.nailgun = NailgunClient(
            self.config.endpoints['nailgun']['host'],
            self.config.endpoints['nailgun']['port'],
        )

        #: a list of ids that have to be removed in case of rollback
        self._rollback_ids = {
            'release': [],
            'notification': [],
        }

    def upgrade(self):
        # clear ids for new upgrade task
        self._rollback_ids = {
            'release': [],
            'notification': [],
        }

        for release in self.releases:
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

    def post_upgrade_actions(self):
        """Nothing to do for this engine.
        """
        pass

    def rollback(self):
        self._rollback_notifications()
        self._rollback_releases()

    def _rollback_releases(self):
        """Remove all releases that are created by current session.
        """
        for release_id in reversed(self._rollback_ids['release']):
            try:
                logger.debug('Removing release with ID=%s', release_id)
                self.nailgun.remove_release(release_id)
            except Exception:
                # try deletion as much as possible
                pass

    def _rollback_notifications(self):
        """Remove all notifications that are created by current session.
        """
        for release_id in reversed(self._rollback_ids['notification']):
            try:
                logger.debug('Removing notification with ID=%s', release_id)
                self.nailgun.remove_notification(release_id)
            except Exception:
                # try deletion as much as possible
                pass
