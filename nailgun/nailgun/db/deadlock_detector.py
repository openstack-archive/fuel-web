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

import six
import threading
import traceback

from nailgun.logger import logger

ALLOWED_LOCKS_CHAINS = [
    ('attributes', 'clusters'),
    ('clusters', 'nodes'),
    ('tasks', 'clusters'),
    ('tasks', 'clusters', 'nodes'),
    ('tasks', 'nodes'),
    ('nodes', 'node_nic_interfaces'),
]


class Lock(object):
    """Locking table info. Includes traceback info of locking call
    """

    @staticmethod
    def _warnings_only():
        """Policy of deadlock detector errors propagation

        NOTE(akislitsky): Temporary function. Should be removed after
        transactions scheme refactoring
        """
        return True

    @staticmethod
    def propagate_exception(exception):
        """Raises or writes exception in dependency of Lock:warnings_only

        :param exception: exception to be propagated
        :return: rises exception or writes log
        """
        if Lock._warnings_only():
            logger.warning("Possible deadlock found: {0}".format(exception))
        else:
            raise exception

    def __init__(self, table, ids):
        self.trace_lst = traceback.extract_stack()
        self.table = table
        self.table = six.text_type(table)
        self.locked_ids = set()
        self.last_locked_id = None
        self.add_ids(ids)

    def add_ids(self, ids):
        if ids is None:
            return

        for id_val in ids:
            # Resource already locked. Has no influence to DB locks.
            if id_val in self.locked_ids:
                continue

            if self.last_locked_id is not None \
                    and self.last_locked_id > id_val:

                exception = ObjectsLockingOrderViolation(
                    self.table, id_val, self.last_locked_id)
                Lock.propagate_exception(exception)

            self.locked_ids.add(id_val)
            self.last_locked_id = id_val

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
                  ', '.join([lock.table for lock in context.locks]),
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
    """Context must be cleaned when transaction ends
    """
    context.locks = []


def handle_lock(table, ids=None):
    """Storing table lock information into locks context.
    :param table: locking table name string value
    """
    lock = Lock(table, ids)

    if not hasattr(context, 'locks'):
        context.locks = []

    # If locking the same table lock is already registered
    if len(context.locks) > 0 and context.locks[-1].table == lock.table:
        return

    # Registering locked table
    context.locks.append(lock)

    # Nothing to check if only one table locked
    if len(context.locks) == 1:
        return

    # Checking lock transition is allowed
    transition = tuple(l.table for l in context.locks)
    if transition not in ALLOWED_LOCKS_CHAINS:
        Lock.propagate_exception(LockTransitionNotAllowedError())


def handle_lock_on_modification(table, ids=None):

    if not hasattr(context, 'locks'):
        context.locks = []

    lock = find_lock(table, strict=False)
    if lock is None:
        handle_lock(table, ids=ids)
    else:
        if lock != context.locks[-1]:
            # Lock is already acquired
            for id_val in ids:
                # Rising error if trying to lock new ids in non last lock
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
    try:
        return next(l for l in context.locks if l.table == table)
    except StopIteration:
        if not strict:
            return None
        else:
            raise LockNotFound("Lock for '{0}' not found".format(table))
