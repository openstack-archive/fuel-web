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

import threading
import traceback

from nailgun.logger import logger
from nailgun.settings import settings

ALLOWED_LOCKS_CHAINS = [
    ('attributes', 'clusters'),
    ('attributes', 'clusters', 'ip_addr_ranges'),
    ('attributes', 'ip_addr_ranges'),
    ('attributes', 'ip_addrs'),
    ('attributes', 'ip_addrs', 'network_groups'),
    ('attributes', 'ip_addr_ranges', 'node_nic_interfaces'),
    ('clusters', 'nodes'),
    ('tasks', 'clusters'),
    ('tasks', 'clusters', 'nodes'),
    ('tasks', 'nodes'),
    ('nodes', 'node_nic_interfaces'),
]


class Lock(object):
    """Locking table info.

    Lock is container for saving information about locked rows in DB table.
    For each table only one Lock object must be created in the 'context'.
    Lock contains table name, values of locked ids (primary keys of locked
    rows), traceback info of locking queries.
    """

    @staticmethod
    def _warnings_only():
        """Policy of deadlock detector errors propagation

        NOTE(akislitsky): Temporary function. Should be removed after
        transactions scheme refactoring. Made as function for mocking inside
        tests.
        """
        return True

    @staticmethod
    def propagate_exception(exception):
        """Raises or writes exception in dependency of Lock:warnings_only

        :param exception: exception to be propagated
        :return: raises exception or writes log
        """
        if Lock._warnings_only():
            if settings.LOG_DEADLOCKS_WARNINGS:
                logger.warning("Possible deadlock found: {0}".
                               format(exception))
        else:
            raise exception

    def __init__(self, table):
        self.trace_lst = traceback.extract_stack()
        self.table = table
        self.locked_ids = set()
        self.last_locked_id = None

    def add_ids(self, ids):
        """Traces ids of locked objects

        :param ids: primary keys collection of locked DB objects
        """
        if ids is None:
            return

        for id_val in ids:
            # Resource already locked. Has no influence to DB locks.
            if id_val is None or id_val in self.locked_ids:
                continue

            # We have agreement on order of locking DB objects:
            # they must be ordered in ascending order by primary key.
            # If we'll try to lock object in wrong order (with
            # id less than already locked) exception will be
            # generated.
            if self.last_locked_id is not None \
                    and self.last_locked_id > id_val:

                exception = ObjectsLockingOrderViolation(
                    self.table, id_val, self.last_locked_id)
                Lock.propagate_exception(exception)

            self.locked_ids.add(id_val)
            self.last_locked_id = id_val

# Thread local storage of current transaction locks.
# Context info is cleared on SqlAlchemy session flush and commit.
context = threading.local()


class DeadlockDetectorError(Exception):
    pass


class LockNotFound(DeadlockDetectorError):
    pass


class TablesLockingOrderViolation(DeadlockDetectorError):
    pass


class ObjectsLockingOrderViolation(DeadlockDetectorError):
    def __init__(self, table, obj_id, last_id):
        super(ObjectsLockingOrderViolation, self).__init__(
            "Trying to lock object id '{0}' in table '{1}'. "
            "Last locked object id '{2}'".format(obj_id, table, last_id)

        )


class LockTransitionNotAllowedError(DeadlockDetectorError):
    def __init__(self):
        msg = "Possible deadlock found while attempting " \
              "to lock table: '{0}'. Lock transition is not allowed: {1}. " \
              "Traceback info: {2}".format(
                  context.locks[-1].table,
                  ', '.join(lock.table for lock in context.locks),
                  self._get_locks_trace()
              )
        Exception.__init__(self, msg)

    def _get_locks_trace(self):
        msg = ""
        for lock in context.locks:
            msg += "\t{0}\n".format('-' * 70)
            msg += "\ttable: {0}\n".format(lock.table)
            msg += "\ttrace: \n"
            for entry in traceback.format_list(lock.trace_lst):
                msg += "\t\t{0}".format(entry)
        return msg


def clean_locks():
    """Context must be cleaned when transaction ends"""
    context.locks = []


def register_lock(table):
    """Registers locking operations on table.

    We have policy on order of locking rows from different tables
    (ALLOWED_LOCKS_CHAINS). If in one place we are locking records
    in tables A, B and in the another in tables B, A, deadlock can
    happen. Here we checking, that locking rows order is not broken.

    :param table: locking table name string value
    :return: returns registered lock
    """
    lock = Lock(table)

    if not hasattr(context, 'locks'):
        context.locks = []

    # If locking the same table lock is already registered
    if len(context.locks) > 0 and context.locks[-1].table == lock.table:
        return lock

    # Registering locked table
    context.locks.append(lock)

    # Nothing to check if only one table locked
    if len(context.locks) == 1:
        return lock

    # Checking lock transition is allowed
    transition = tuple(l.table for l in context.locks)
    if transition not in ALLOWED_LOCKS_CHAINS:
        Lock.propagate_exception(LockTransitionNotAllowedError())

    return lock


def handle_lock(table, ids=None):
    """Traces table and objects ids on modification or locking operations

    :param table: locking table name string value
    :param ids: ids of locking objects
    """

    if not hasattr(context, 'locks'):
        context.locks = []

    lock = find_lock(table, strict=False)
    if lock is None:
        # Register lock and check tables order for locking queries
        # is not broken
        lock = register_lock(table)
    else:
        # In some cases we can try to acquire locks on already locked
        # rows. In this case on the DB level we already have locks on
        # these rows, thus this operation is legal and can't raise
        # deadlock. For last table in context order of locking ids
        # will be checked below in 'lock.add_ids' call. Thus here we
        # perform checking only for locks in tables, traced before the
        # last one.
        if ids is not None and lock != context.locks[-1]:
            # Lock is already acquired
            for id_val in ids:
                # Rising error if trying to lock new ids in non last lock.
                if id_val not in lock.locked_ids:
                    lock_chain = ', '.join(l.table for l in context.locks)
                    exception = TablesLockingOrderViolation(
                        "Trying to lock {0} in {1}. "
                        "Current locks chain: {2}. "
                        "Already locked ids for {1}: {3}".format(
                            id_val, table, lock_chain, lock.locked_ids
                        ))
                    Lock.propagate_exception(exception)
    lock.add_ids(ids)


def find_lock(table, strict=True):
    """Finds lock for table

    :param table: table name
    :param strict: raise error if lock is not found
    :return: lock info for table
    """
    lock = next((l for l in context.locks if l.table == table), None)
    if lock is None and strict:
        locks_in_tables = list(lock.table for lock in context.locks)
        raise LockNotFound("Lock for '{0}' not found. "
                           "Current locks list: {1}".
                           format(table, locks_in_tables))
    return lock
