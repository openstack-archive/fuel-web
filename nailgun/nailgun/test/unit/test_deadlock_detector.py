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

from threading import current_thread
from threading import Event
from threading import Thread

from nailgun.db import db
from nailgun.db import deadlock_detector
from nailgun.db.deadlock_detector import LockTransitionNotAllowedError
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import Release
from nailgun.db.sqlalchemy.models import Task
from nailgun.test.base import BaseTestCase


class TestDeadlockDetector(BaseTestCase):

    def tearDown(self):
        super(TestDeadlockDetector, self).tearDown()
        db().rollback()

    def test_no_locks(self):
        len_exp = len(deadlock_detector.context.locks)
        db().query(Node).all()
        self.assertEquals(len_exp, len(deadlock_detector.context.locks))
        db().query(Node).all()
        db().query(Cluster).all()
        self.assertEquals(len_exp, len(deadlock_detector.context.locks))

    def test_lock_same_table(self):
        # Cleaning locks
        db().commit()
        # Adding locks
        db().query(Node).with_lockmode('update').all()
        db().query(Node).with_lockmode('update').all()
        db().query(Node).with_lockmode('update').all()
        # Checking only one lock has been added
        self.assertEquals(1, len(deadlock_detector.context.locks))
        db().commit()

    def test_lock_cleaned_on_commit(self):
        db().query(Cluster).with_lockmode('update').all()
        db().query(Node).with_lockmode('update').all()
        self.assertTrue(len(deadlock_detector.context.locks) > 0)
        db().commit()
        self.assertEquals(0, len(deadlock_detector.context.locks))

    def test_lock_cleaned_on_rollback(self):
        db().query(Cluster).with_lockmode('update').all()
        db().query(Node).with_lockmode('update').all()
        self.assertTrue(len(deadlock_detector.context.locks) > 0)
        db().rollback()
        self.assertEquals(0, len(deadlock_detector.context.locks))

    def test_unknown_locks_chain_failed(self):
        db().query(Release).with_lockmode('update').all()
        self.assertRaises(
            LockTransitionNotAllowedError,
            db().query(Node).with_lockmode, 'update'
        )
        db().rollback()

        db().query(Task).with_lockmode('update').all()
        db().query(Cluster).with_lockmode('update').all()
        db().query(Node).with_lockmode('update').all()
        self.assertRaises(
            LockTransitionNotAllowedError,
            db().query(Task).with_lockmode, 'update'
        )
        db().rollback()

    def test_locks_chain(self):
        db().query(Cluster).with_lockmode('update').all()
        db().query(Node).with_lockmode('update').all()
        db().commit()

        db().query(Cluster).with_lockmode('update').all()
        db().query(Cluster).with_lockmode('update').all()
        db().query(Node).with_lockmode('update').all()
        db().query(Node).with_lockmode('update').all()
        db().query(Node).with_lockmode('update').all()
        db().commit()

    def lock_tables(self, objects, results, event, threads_num):
        try:
            for obj in objects:
                db().query(obj).with_lockmode('update').all()
        except Exception:
            pass
        finally:
            results.append(current_thread())
            if len(results) == threads_num:
                event.set()

        # Waiting when all objects will locked in all threads
        event.wait()

        # Checking locks context isolation from other threads
        try:
            self.assertEquals(
                len(objects),
                len(deadlock_detector.context.locks)
            )
            results.append(True)
        except Exception as e:
            results.append(False)
            raise e
        finally:
            db().commit()

    def test_lock_context_isolation_in_threads(self):
        results = []
        objects_for_locks = (
            (Cluster, Node),
            (Node, Cluster),
            (Release,)
        )
        threads = []
        # Barrier synchronization primitive had implemented only in Python 3
        event = Event()
        for objects in objects_for_locks:
            t = Thread(
                target=self.lock_tables,
                args=(objects, results, event, len(objects_for_locks))
            )
            t.start()
            threads.append(t)
        map(Thread.join, threads)
        self.assertTrue(all(results))
