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

import mock
from threading import current_thread
from threading import Event
from threading import Thread

from sqlalchemy.orm import exc

from nailgun import consts
from nailgun.db import db
from nailgun.db import deadlock_detector as dd
from nailgun.db.sqlalchemy import models
from nailgun.test.base import BaseTestCase


class TestDeadlockDetector(BaseTestCase):

    patchers = [
        mock.patch('nailgun.db.deadlock_detector.Lock._warnings_only',
                   return_value=False)
    ]

    @classmethod
    def setUpClass(cls):
        super(TestDeadlockDetector, cls).setUpClass()
        for patcher in cls.patchers:
            patcher.start()

    @classmethod
    def tearDownClass(cls):
        super(TestDeadlockDetector, cls).tearDownClass()
        for patcher in cls.patchers:
            patcher.stop()

    def tearDown(self):
        super(TestDeadlockDetector, self).tearDown()
        db().rollback()

    def test_no_locks(self):
        len_exp = len(dd.context.locks)
        db().query(models.Node).all()
        self.assertEquals(len_exp, len(dd.context.locks))
        db().query(models.Node).all()
        db().query(models.Cluster).all()
        self.assertEquals(len_exp, len(dd.context.locks))

    def test_lock_same_table(self):
        # Cleaning locks
        db().commit()
        # Adding locks
        db().query(models.Node).with_lockmode('update').all()
        db().query(models.Node).with_lockmode('update').all()
        db().query(models.Node).with_lockmode('update').all()
        # Checking only one lock has been added
        self.assertEquals(1, len(dd.context.locks))
        db().commit()

    def test_lock_cleaned_on_commit(self):
        db().query(models.Cluster).with_lockmode('update').all()
        db().query(models.Node).with_lockmode('update').all()
        self.assertGreater(len(dd.context.locks), 0)
        db().commit()
        self.assertEquals(0, len(dd.context.locks))

    def test_lock_not_cleaned_on_flush(self):
        db().query(models.Cluster).with_lockmode('update').\
            order_by('id').all()
        self.assertGreater(len(dd.context.locks), 0)
        db().flush()
        self.assertGreater(len(dd.context.locks), 0)

    def test_lock_cleaned_on_rollback(self):
        db().query(models.Cluster).with_lockmode('update').all()
        db().query(models.Node).with_lockmode('update').all()
        self.assertGreater(len(dd.context.locks), 0)
        db().rollback()
        self.assertEquals(0, len(dd.context.locks))

    def test_unknown_locks_chain_failed(self):
        db().query(models.Release).with_lockmode('update').all()
        self.assertRaises(
            dd.LockTransitionNotAllowedError,
            db().query(models.Node).with_lockmode, 'update'
        )
        db().rollback()

        db().query(models.Task).with_lockmode('update').all()
        db().query(models.Cluster).with_lockmode('update').all()
        db().query(models.Node).with_lockmode('update').all()
        self.assertRaises(
            dd.LockTransitionNotAllowedError,
            db().query(models.Task).with_lockmode, 'update'
        )
        db().rollback()

    def test_locks_chain(self):
        db().query(models.Cluster).with_lockmode('update').all()
        db().query(models.Node).with_lockmode('update').all()
        db().commit()

        db().query(models.Cluster).with_lockmode('update').all()
        db().query(models.Cluster).with_lockmode('update').all()
        db().query(models.Node).with_lockmode('update').all()
        db().query(models.Node).with_lockmode('update').all()
        db().query(models.Node).with_lockmode('update').all()
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
                len(dd.context.locks)
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
            (models.Cluster, models.Node),
            (models.Node, models.Cluster),
            (models.Release,)
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
        for thread in threads:
            thread.join()
        self.assertTrue(all(results))

    def test_find_lock(self):
        self.assertIsNone(dd.find_lock('xxx', strict=False))
        db().query(models.Release).with_lockmode('update').all()
        lock = dd.find_lock(models.Release.__tablename__, strict=True)
        self.assertIsNotNone(lock)
        self.assertEqual(models.Release.__tablename__, lock.table)

    def test_find_lock_failed(self):
        db().query(models.Release).with_lockmode('update').all()
        self.assertRaisesWithMessage(
            dd.LockNotFound,
            "Lock for 'nodes' not found. Current locks list: ['releases']",
            dd.find_lock, models.Node.__tablename__, strict=True)

    def test_ids_traced_select_from_single_table(self):
        self.env.create_nodes(2)
        nodes = db().query(models.Node).order_by('id').\
            with_lockmode('update').all()
        lock = dd.find_lock(models.Node.__tablename__)
        self.assertEqual(lock.locked_ids, set(o.id for o in nodes))

    def test_select_failed_with_wrong_order(self):
        self.env.create_nodes(2)
        with self.assertRaises(dd.ObjectsLockingOrderViolation):
            db().query(models.Node).order_by(models.Node.id.desc()).\
                with_lockmode('update').all()

    def test_locking_already_locked_objects(self):
        self.env.create_nodes(2)
        nodes = db().query(models.Node).order_by('id').\
            with_lockmode('update').all()
        lock = dd.find_lock(models.Node.__tablename__)
        self.assertEqual(lock.locked_ids, set(o.id for o in nodes))

        db().query(models.Node).with_lockmode('update').get(nodes[0].id)
        self.assertEqual(lock.locked_ids, set(o.id for o in nodes))

    def test_ids_traced_select_from_different_tables(self):
        self.env.create_nodes(3)
        clusters = db().query(models.Cluster).order_by('id').\
            with_lockmode('update').all()
        nodes = db().query(models.Node).order_by('id').\
            with_lockmode('update').all()
        nodes_lock = dd.find_lock(models.Node.__tablename__)
        clusters_lock = dd.find_lock(models.Cluster.__tablename__)

        self.assertEqual(nodes_lock.locked_ids, set(o.id for o in nodes))
        self.assertEqual(clusters_lock.locked_ids, set(o.id for o in clusters))

    def test_id_traced_in_get(self):
        # Check lock registered for not found node
        node = db().query(models.Node).with_lockmode('update').get(0)
        self.assertIsNone(node)
        nodes_lock = dd.find_lock(models.Node.__tablename__, strict=False)
        self.assertIsNotNone(nodes_lock)
        self.assertEqual(set(), nodes_lock.locked_ids)

        # Check id traced
        self.env.create_nodes(2)

        # Locking clusters
        db().query(models.Cluster).with_lockmode('update')

        # Locking nodes
        nodes = db().query(models.Node).order_by('id').all()

        # Locking in ASC order is ok
        for node in nodes:
            db().query(models.Node).with_lockmode('update').get(node.id)

        nodes_lock = dd.find_lock(models.Node.__tablename__)
        self.assertEqual(nodes_lock.locked_ids, set(o.id for o in nodes))

    def test_wrong_order_in_get_failed(self):
        self.env.create_nodes(2)

        nodes = db().query(models.Node).order_by('-id').all()
        db().query(models.Node).with_lockmode('update').get(nodes[0].id)
        with self.assertRaises(dd.ObjectsLockingOrderViolation):
            db().query(models.Node).with_lockmode('update').get(nodes[1].id)

    def test_updating_already_locked_object(self):
        cluster = self.env.create_cluster()
        self.env.create_nodes(2)
        self.env.create_cluster()
        self.assertGreater(len(self.env.clusters), 1)

        # Locking clusters
        db().query(models.Cluster).order_by('id').with_lockmode('update').all()
        # Locking nodes
        db().query(models.Node).order_by('id').with_lockmode('update').all()

        # Lock is allowed
        cluster.status = consts.CLUSTER_STATUSES.error

    def test_id_traced_on_updating_object(self):
        cluster = self.env.create_cluster()
        self.env.create_nodes(2)
        self.env.create_cluster()
        self.assertGreater(len(self.env.clusters), 1)

        # Updating cluster
        cluster.status = consts.CLUSTER_STATUSES.error

        # Checking locked id trace
        cluster_lock = dd.find_lock(models.Cluster.__tablename__)
        self.assertEqual(cluster_lock.locked_ids, set([cluster.id]))

        # Updating nodes
        nodes = db().query(models.Node).order_by('id').all()
        for node in nodes:
            node.status = consts.NODE_STATUSES.error

        # Checking locked ids trace
        node_lock = dd.find_lock(models.Node.__tablename__)
        self.assertEqual(node_lock.locked_ids, set(o.id for o in nodes))

    def test_updating_ids_in_wrong_order_failed(self):
        self.env.create_nodes(2)

        nodes = db().query(models.Node).order_by('-id').all()
        with self.assertRaises(dd.ObjectsLockingOrderViolation):
            for node in nodes:
                node.status = consts.NODE_STATUSES.error

    def test_lock_ids_in_non_last_lock_failed(self):
        cluster = self.env.create_cluster()
        self.env.create_nodes(2)
        another_cluster = self.env.create_cluster()
        self.assertGreater(len(self.env.clusters), 1)

        # Tracing cluster modification
        cluster.status = consts.CLUSTER_STATUSES.error

        cluster_lock = dd.find_lock(models.Cluster.__tablename__)
        self.assertEqual(cluster_lock.locked_ids, set([cluster.id]))

        # Tracing nodes modification
        db().query(models.Node).with_lockmode('update').order_by('id').all()

        # Trying to lock ids in non last lock
        last_lock = dd.context.locks[-1]
        self.assertNotEqual(cluster_lock, last_lock)

        with self.assertRaises(dd.TablesLockingOrderViolation):
            another_cluster.status = consts.CLUSTER_STATUSES.error

    def test_bulk_update_query_ids_traced(self):
        self.env.create_nodes(2)
        self.assertIsNone(dd.find_lock(
            models.Node.__tablename__, strict=False))

        node = self.env.nodes[0]
        db().query(models.Node).filter(models.Node.id == node.id).\
            update({'status': consts.NODE_STATUSES.error})

        nodes_lock = dd.find_lock(models.Node.__tablename__, strict=False)
        self.assertIsNotNone(nodes_lock)
        self.assertEqual(nodes_lock.locked_ids, set([node.id]))

    def test_bulk_delete_query_ids_traced(self):
        self.env.create_nodes(2)

        node = self.env.nodes[0]
        db().query(models.Node).filter(models.Node.id == node.id).\
            delete()
        node_lock = dd.find_lock(models.Node.__tablename__, strict=False)
        self.assertIsNotNone(node_lock)
        self.assertEqual(node_lock.locked_ids, set([node.id]))

    def test_id_traced_for_fetching_first(self):
        # Check lock registered for not found node
        node = db().query(models.Node).with_lockmode('update').\
            order_by('id').first()
        self.assertIsNone(node)
        node_lock = dd.find_lock(models.Node.__tablename__, strict=False)
        self.assertIsNotNone(node_lock)
        self.assertEqual(set(), node_lock.locked_ids)

        # Check id traced
        self.env.create_nodes(2)
        node = db().query(models.Node).with_lockmode('update').\
            order_by('id').first()
        self.assertIsNotNone(node)
        self.assertIn(node.id, node_lock.locked_ids)

    def test_lock_failed_on_wrong_order_for_fetching_first(self):
        self.env.create_nodes(2)

        nodes = db().query(models.Node).order_by('-id').all()

        db().query(models.Node).with_lockmode('update').\
            filter(models.Node.id == nodes[0].id).first()

        with self.assertRaises(dd.ObjectsLockingOrderViolation):
            db().query(models.Node).with_lockmode('update').\
                filter(models.Node.id == nodes[1].id).first()

    def test_id_traced_for_fetching_one(self):
        # Check lock registered for not found node
        with self.assertRaises(exc.NoResultFound):
            db().query(models.Node).with_lockmode('update').\
                filter(models.Node.id == 0).one()

        # We have registered lock due to processing with_lockmode
        node_lock = dd.find_lock(models.Node.__tablename__, strict=False)
        self.assertIsNotNone(node_lock)
        self.assertEqual(set(), node_lock.locked_ids)

        # Check id traced
        self.env.create_nodes(2)
        node = self.env.nodes[0]
        node = db().query(models.Node).with_lockmode('update').\
            filter(models.Node.id == node.id).one()

        self.assertIsNotNone(node)
        self.assertIn(node.id, node_lock.locked_ids)

    def test_lock_failed_on_wrong_order_for_fetching_one(self):
        self.env.create_nodes(2)

        nodes = db().query(models.Node).order_by('-id').all()

        db().query(models.Node).with_lockmode('update').\
            filter(models.Node.id == nodes[0].id).one()

        with self.assertRaises(dd.ObjectsLockingOrderViolation):
            db().query(models.Node).with_lockmode('update').\
                filter(models.Node.id == nodes[1].id).one()

    def test_id_traced_on_object_deletion(self):
        self.env.create_nodes(2)

        node = self.env.nodes[0]
        node_id = node.id
        db().delete(node)
        node_lock = dd.find_lock(models.Node.__tablename__)
        self.assertEqual(node_lock.locked_ids, set([node_id]))

    def test_deletion_already_locked_object(self):
        self.env.create_cluster()
        self.env.create_nodes(2)

        cluster = db().query(models.Cluster).with_lockmode('update').\
            order_by('id').first()
        db().query(models.Node).with_lockmode('update').\
            order_by('id').all()

        db().delete(cluster)

    def test_deletion_in_wrong_order_failed(self):
        self.env.create_cluster()
        self.env.create_nodes(2)

        nodes = db().query(models.Node).order_by('-id').all()
        db().delete(nodes[0])

        with self.assertRaises(dd.ObjectsLockingOrderViolation):
            db().delete(nodes[1])

    def test_deletion_with_non_last_lock_failed(self):
        old_cluster = self.env.create_cluster()
        self.env.create_nodes(2)

        new_cluster = self.env.create_cluster()

        # Locking clusters and nodes
        db().query(models.Cluster).with_lockmode('update').\
            get(old_cluster.id)
        db().query(models.Node).with_lockmode('update').\
            order_by('id').all()

        # Trying to delete not locked cluster with non last lock
        last_lock = dd.context.locks[-1]
        cluster_lock = dd.find_lock(models.Cluster.__tablename__)
        self.assertNotEqual(cluster_lock, last_lock)

        with self.assertRaises(dd.TablesLockingOrderViolation):
            db().delete(new_cluster)
