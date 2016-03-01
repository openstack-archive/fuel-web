# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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

import datetime

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.errors import errors
from nailgun.logger import logger

from nailgun.objects import NailgunObject
from nailgun.objects.cluster import Cluster


class ClusterLocks(NailgunObject):
    """Cluster attributes object."""

    model = models.ClusterLocks

    @classmethod
    def acquire_lock(cls, cluster, timeout, lock_type=None):
        """Acquires lock for cluster.

        :param cluster: the Cluster instance
        :param timeout: the lock timeout
        :param lock_type: the lock type, 'exclusive' is used by default
        :returns: lock id
        """
        logger.info('Try to lock cluster: "%d"', cluster.id)
        now = datetime.datetime.now()
        Cluster.get_by_uid(cluster.id, lock_for_update=True)
        existing = db().query(cls.model).filter(
            cls.model.cluster_id == cluster.id,
            cls.model.expiration >= now
        ).with_lockmode('read').first()

        if existing:
            raise errors.CannotAcquireLock(
                'The cluster has been locked already. Cluster: "{0}"'
                .format(cluster.id)
            )
        # TODO(bgaifullin) need separate process to manage expired locks
        cls.drain_expired(cluster)
        return cls.create({
            'cluster_id': cluster,
            'expiration': cls._add_timedelta(now, timeout),
            'type': lock_type or consts.LOCK_TYPES.exclusive
        }).id

    @classmethod
    def refresh_lock(cls, lock_id, timeout):
        """Acquires lock for cluster.

        :param lock_id: the ID of lock
        :param timeout: the lock timeout
        """

        logger.info('Try to refresh lock: "%d"', lock_id)
        now = datetime.datetime.now()
        lock = cls.get_by_uid(lock_id, lock_for_update=True)

        if lock.expiration < now:
            raise errors.CannotRefreshLock(
                "The lock for cluster: {0} was expired"
            )
        lock.expiration = cls._add_timedelta(now, timeout)

    @classmethod
    def release_lock(cls, lock_id):
        """Release the lock.

        :param lock_id: the ID of lock
        """

        logger.info("Release the lock: %d", lock_id)

    @classmethod
    def drain_expired(cls, cluster):
        """Cleans up expired locks.

        :param cluster: The Cluster object
        """
        db().query(cls.model).filter(
            cls.model.cluster_id == cluster.id,
            cls.model.expiration < datetime.datetime.now()
        ).delete()

    @classmethod
    def _add_timedelta(cls, timestamp, delta):
        if not isinstance(delta, datetime.timedelta):
            delta = datetime.timedelta(seconds=delta)
        return timestamp + delta
