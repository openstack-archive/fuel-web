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


ALLOWED_LOCKS_CHAINS = [
    ('clusters', 'nodes'),
    ('tasks', 'clusters'),
    ('tasks', 'clusters', 'nodes'),
    ('tasks', 'nodes'),
]


class Lock(object):
    """Locking table info. Includes traceback info of locking call
    """

    def __init__(self, table):
        self.trace_lst = traceback.extract_stack()
        self.table = table


context = threading.local()


class LockTransitionNotAllowedError(Exception):
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


def handle_lock(table):
    """Storing table lock information into locks context.
    :param table: locking table name string value
    """
    lock = Lock(table)

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
    transition = (context.locks[-2].table, context.locks[-1].table)
    if transition not in ALLOWED_LOCKS_CHAINS:
        raise LockTransitionNotAllowedError()
