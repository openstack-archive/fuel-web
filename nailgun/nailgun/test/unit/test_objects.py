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

import copy
from itertools import cycle
from itertools import ifilter

from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse

from nailgun.errors import errors

from nailgun import consts

from nailgun.db import NoCacheQuery
from nailgun.db.sqlalchemy.models import Task

from nailgun.openstack.common import jsonutils

from nailgun import objects


class TestObjects(BaseIntegrationTest):

    def test_filter_by(self):
        names = cycle('ABCD')
        os = cycle(['CentOS', 'Ubuntu'])
        for i in xrange(12):
            self.env.create_release(
                name=names.next(),
                operating_system=os.next()
            )

        # filtering query - returns query
        query_filtered = objects.ReleaseCollection.filter_by(
            objects.ReleaseCollection.all(),
            name="A",
            operating_system="CentOS"
        )
        self.assertIsInstance(query_filtered, NoCacheQuery)
        self.assertEqual(
            objects.ReleaseCollection.count(query_filtered),
            3
        )
        for r in query_filtered:
            self.assertEqual(r.name, "A")
            self.assertEqual(r.operating_system, "CentOS")

        # filtering iterable - returns ifilter
        iterable_filtered = objects.ReleaseCollection.filter_by(
            list(objects.ReleaseCollection.all()),
            name="A",
            operating_system="CentOS"
        )
        self.assertIsInstance(iterable_filtered, ifilter)
        self.assertEqual(
            objects.ReleaseCollection.count(iterable_filtered),
            3
        )
        for r in iterable_filtered:
            self.assertEqual(r.name, "A")
            self.assertEqual(r.operating_system, "CentOS")

        iterable_filtered = objects.ReleaseCollection.filter_by(
            list(),
            name="A",
        )
        self.assertIsInstance(iterable_filtered, ifilter)
        self.assertEquals(0, len(list(iterable_filtered)))

    def test_filter_by_not(self):
        names = cycle('ABCDE')
        os = cycle(['CentOS', 'Ubuntu'])

        # create releases: we'll have only two releases with both
        # name A and operating_system CentOS
        for i in xrange(12):
            self.env.create_release(
                name=names.next(),
                operating_system=os.next()
            )

        # filtering query - returns query
        query_filtered = objects.ReleaseCollection.filter_by_not(
            objects.ReleaseCollection.all(),
            name="A",
            operating_system="CentOS"
        )
        self.assertIsInstance(query_filtered, NoCacheQuery)
        self.assertEqual(
            objects.ReleaseCollection.count(query_filtered),
            10
        )
        for r in query_filtered:
            if r.name == "A":
                self.assertNotEqual(r.operating_system, "CentOS")
            elif r.operating_system == "CentOS":
                self.assertNotEqual(r.name, "A")

        # filtering iterable - returns ifilter
        iterable_filtered = objects.ReleaseCollection.filter_by_not(
            list(objects.ReleaseCollection.all()),
            name="A",
            operating_system="CentOS"
        )
        self.assertIsInstance(iterable_filtered, ifilter)
        self.assertEqual(
            objects.ReleaseCollection.count(iterable_filtered),
            10
        )
        for r in iterable_filtered:
            if r.name == "A":
                self.assertNotEqual(r.operating_system, "CentOS")
            elif r.operating_system == "CentOS":
                self.assertNotEqual(r.name, "A")


class TestNodeObject(BaseIntegrationTest):

    def test_adding_to_cluster_kernel_params_centos(self):
        self.env.create(
            release_kwargs={
                "operating_system": consts.RELEASE_OS.centos
            },
            cluster_kwargs={},
            nodes_kwargs=[
                {"role": "controller"}
            ]
        )
        node_db = self.env.nodes[0]
        self.assertEqual(
            objects.Node.get_kernel_params(node_db),
            (
                'console=ttyS0,9600 '
                'console=tty0 '
                'biosdevname=0 '
                'crashkernel=none '
                'rootdelay=90 '
                'nomodeset'
            )
        )

    def test_adding_to_cluster_kernel_params_ubuntu(self):
        self.env.create(
            release_kwargs={
                "operating_system": consts.RELEASE_OS.ubuntu,
                "attributes_metadata": {
                    "editable": {
                        "kernel_params": {
                            "kernel": {
                                "value": (
                                    "console=ttyS0,9600 "
                                    "console=tty0 "
                                    "rootdelay=90 "
                                    "nomodeset"
                                )
                            }
                        }
                    }
                }
            },
            cluster_kwargs={},
            nodes_kwargs=[
                {"role": "controller"}
            ]
        )
        node_db = self.env.nodes[0]
        self.assertEqual(
            objects.Node.get_kernel_params(node_db),
            (
                'console=ttyS0,9600 '
                'console=tty0 '
                'rootdelay=90 '
                'nomodeset'
            )
        )

    def test_get_kernel_params_overwriten(self):
        """Test verifies that overwriten kernel params will be returned."""
        self.env.create(
            nodes_kwargs=[
                {"role": "controller"}
            ])
        additional_kernel_params = 'intel_iommu=true'
        default_kernel_params = objects.Cluster.get_default_kernel_params(
            self.env.clusters[0])
        kernel_params = '{0} {1}'.format(default_kernel_params,
                                         additional_kernel_params)
        self.env.nodes[0].kernel_params = kernel_params
        self.assertNotEqual(
            objects.Node.get_kernel_params(self.env.nodes[0]),
            default_kernel_params)
        self.assertEqual(
            objects.Node.get_kernel_params(self.env.nodes[0]),
            kernel_params)

    def test_should_have_public(self):
        self.env.create(
            cluster_kwargs={
                'net_provider': 'neutron'},
            nodes_kwargs=[
                {'roles': ['controller', 'cinder'], 'pending_addition': True},
                {'roles': ['compute', 'cinder'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True},
                {'roles': [], 'pending_roles': ['cinder'],
                 'pending_addition': True},
                {'roles': [], 'pending_roles': ['controller'],
                 'pending_addition': True}])

        cluster = self.env.clusters[0]
        attrs = cluster.attributes.editable
        self.assertEqual(
            attrs['public_network_assignment']['assign_to_all_nodes']['value'],
            False
        )

        nodes_w_public_count = 0
        for node in self.env.nodes:
            nodes_w_public_count += int(objects.Node.should_have_public(node))
        self.assertEqual(nodes_w_public_count, 2)

        attrs['public_network_assignment']['assign_to_all_nodes']['value'] = \
            True
        resp = self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster.id}),
            params=jsonutils.dumps({'editable': attrs}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)

        nodes_w_public_count = 0
        for node in self.env.nodes:
            nodes_w_public_count += int(objects.Node.should_have_public(node))
        self.assertEqual(nodes_w_public_count, 5)

    def test_removing_from_cluster(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"role": "controller"}
            ]
        )
        node_db = self.env.nodes[0]
        node2_db = self.env.create_node()
        objects.Node.remove_from_cluster(node_db)
        self.assertEqual(node_db.cluster_id, None)
        self.assertEqual(node_db.roles, [])
        self.assertEqual(node_db.pending_roles, [])

        exclude_fields = [
            "id",
            "mac",
            "meta",
            "name",
            "agent_checksum"
        ]
        fields = set(
            objects.Node.schema["properties"].keys()
        ) ^ set(exclude_fields)

        for f in fields:
            self.assertEqual(
                getattr(node_db, f),
                getattr(node2_db, f)
            )

    def test_removing_from_cluster_idempotent(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"role": "controller"}
            ]
        )
        node_db = self.env.nodes[0]
        objects.Node.remove_from_cluster(node_db)

        try:
            objects.Node.remove_from_cluster(node_db)
        except Exception as exc:
            self.fail("Node removing is not idempotent: {0}!".format(exc))

    def test_update_by_agent(self):
        node_db = self.env.create_node()
        data = {
            "status": node_db.status,
            "meta": copy.deepcopy(node_db.meta),
            "mac": node_db.mac,
        }

        # test empty disks handling
        data["meta"]["disks"] = []
        objects.Node.update_by_agent(node_db, copy.deepcopy(data))
        self.assertNotEqual(node_db.meta["disks"], data["meta"]["disks"])

        # test status handling
        for status in ('provisioning', 'error'):
            node_db.status = status
            data["status"] = "discover"
            objects.Node.update_by_agent(node_db, copy.deepcopy(data))

            self.assertEqual(node_db.status, status)

    def test_node_roles_to_pending_roles(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {'role': 'controller'}
            ]
        )
        node_db = self.env.nodes[0]
        node = objects.Node.get_by_uid(node_db.id, fail_if_not_found=True)
        self.assertEquals(['controller'], node.roles)
        self.assertEquals([], node.pending_roles)
        # Checking roles moved
        objects.Node.move_roles_to_pending_roles(node)
        self.assertEquals([], node.roles)
        self.assertEquals(['controller'], node.pending_roles)
        # Checking second moving has no affect
        objects.Node.move_roles_to_pending_roles(node)
        self.assertEquals([], node.roles)
        self.assertEquals(['controller'], node.pending_roles)

    def test_objects_order_by(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {'role': 'z'},
                {'role': 'a'},
                {'role': 'b'},
                {'role': 'controller'},
                {'role': 'controller'},
                {'role': 'controller'},
                {'role': 'controller'},
                {'role': 'controller'}
            ]
        )

        # Checking nothing to be sorted
        nodes = objects.NodeCollection.order_by(None, 'id')
        self.assertEquals(None, nodes)

        iterable = ['b', 'a']
        nodes = objects.NodeCollection.order_by(iterable, ())
        self.assertEquals(iterable, nodes)

        # Checking query ASC ordering applied
        q_nodes = objects.NodeCollection.filter_by(None)
        nodes = objects.NodeCollection.order_by(q_nodes, 'id').all()
        self.assertListEqual(nodes, sorted(nodes, key=lambda x: x.id))
        # Checking query DESC ordering applied
        q_nodes = objects.NodeCollection.filter_by(None)
        nodes = objects.NodeCollection.order_by(q_nodes, '-id').all()
        self.assertListEqual(
            nodes,
            sorted(nodes, key=lambda x: x.id, reverse=True)
        )

        # Checking iterable ASC ordering applied
        nodes = objects.NodeCollection.filter_by(None).all()
        ordered_nodes = objects.NodeCollection.order_by(nodes, 'role')
        self.assertListEqual(
            ordered_nodes,
            sorted(nodes, key=lambda x: x.role)
        )

        # Checking iterable DESC ordering applied
        nodes = objects.NodeCollection.filter_by(None).all()
        ordered_nodes = objects.NodeCollection.order_by(nodes, '-id')
        self.assertListEqual(
            ordered_nodes,
            sorted(nodes, key=lambda x: x.id, reverse=True)
        )

        # Checking order by number of fields
        nodes = objects.NodeCollection.filter_by(None).all()
        ordered_nodes = objects.NodeCollection.order_by(nodes, ('-id', 'role'))
        self.assertListEqual(
            ordered_nodes,
            sorted(
                sorted(nodes, key=lambda x: x.id, reverse=True),
                key=lambda x: x.role
            )
        )

    def test_eager_nodes_handlers(self):
        """Test verifies that custom handler works and returns correct
        number of nodes.
        """
        nodes_count = 10
        self.env.create_nodes(nodes_count)
        nodes_db = objects.NodeCollection.eager_nodes_handlers(None)
        self.assertEqual(nodes_db.count(), nodes_count)


class TestTaskObject(BaseIntegrationTest):

    def setUp(self):
        super(TestTaskObject, self).setUp()
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller']},
                {'roles': ['compute']},
                {'roles': ['cinder']}])

    def _node_should_be_error_with_type(self, node, error_type):
        self.assertEquals(node.status, 'error')
        self.assertEquals(node.error_type, error_type)
        self.assertEquals(node.progress, 0)

    def _nodes_should_not_be_error(self, nodes):
        for node in nodes:
            self.assertEquals(node.status, 'discover')

    @property
    def cluster(self):
        return self.env.clusters[0]

    def test_update_nodes_to_error_if_deployment_task_failed(self):
        self.cluster.nodes[0].status = 'deploying'
        self.cluster.nodes[0].progress = 12
        task = Task(name='deployment', cluster=self.cluster, status='error')
        self.db.add(task)
        self.db.flush()

        objects.Task._update_cluster_data(task)
        self.db.flush()

        self.assertEquals(self.cluster.status, 'error')
        self._node_should_be_error_with_type(self.cluster.nodes[0], 'deploy')
        self._nodes_should_not_be_error(self.cluster.nodes[1:])

    def test_update_cluster_to_error_if_deploy_task_failed(self):
        task = Task(name='deploy', cluster=self.cluster, status='error')
        self.db.add(task)
        self.db.flush()

        objects.Task._update_cluster_data(task)
        self.db.flush()

        self.assertEquals(self.cluster.status, 'error')

    def test_update_nodes_to_error_if_provision_task_failed(self):
        self.cluster.nodes[0].status = 'provisioning'
        self.cluster.nodes[0].progress = 12
        task = Task(name='provision', cluster=self.cluster, status='error')
        self.db.add(task)
        self.db.flush()

        objects.Task._update_cluster_data(task)
        self.db.flush()

        self.assertEquals(self.cluster.status, 'error')
        self._node_should_be_error_with_type(self.cluster.nodes[0],
                                             'provision')
        self._nodes_should_not_be_error(self.cluster.nodes[1:])

    def test_update_cluster_to_operational(self):
        task = Task(name='deploy', cluster=self.cluster, status='ready')
        self.db.add(task)
        self.db.flush()

        objects.Task._update_cluster_data(task)
        self.db.flush()

        self.assertEquals(self.cluster.status, 'operational')

    def test_update_if_parent_task_is_ready_all_nodes_should_be_ready(self):
        for node in self.cluster.nodes:
            node.status = 'ready'
            node.progress = 100

        self.cluster.nodes[0].status = 'deploying'
        self.cluster.nodes[0].progress = 24

        task = Task(name='deploy', cluster=self.cluster, status='ready')
        self.db.add(task)
        self.db.flush()

        objects.Task._update_cluster_data(task)
        self.db.flush()

        self.assertEquals(self.cluster.status, 'operational')

        for node in self.cluster.nodes:
            self.assertEquals(node.status, 'ready')
            self.assertEquals(node.progress, 100)

    def test_update_cluster_status_if_task_was_already_in_error_status(self):
        for node in self.cluster.nodes:
            node.status = 'provisioning'
            node.progress = 12

        task = Task(name='provision', cluster=self.cluster, status='error')
        self.db.add(task)
        self.db.flush()

        data = {'status': 'error', 'progress': 100}

        objects.Task.update(task, data)
        self.db.flush()

        self.assertEquals(self.cluster.status, 'error')
        self.assertEquals(task.status, 'error')

        for node in self.cluster.nodes:
            self.assertEquals(node.status, 'error')
            self.assertEquals(node.progress, 0)

    def test_do_not_set_cluster_to_error_if_validation_failed(self):
        for task_name in ['check_before_deployment', 'check_networks']:
            supertask = Task(
                name='deploy',
                cluster=self.cluster,
                status='error')

            check_task = Task(
                name=task_name,
                cluster=self.cluster,
                status='error')

            supertask.subtasks.append(check_task)
            self.db.add(check_task)
            self.db.flush()

            objects.Task._update_cluster_data(supertask)
            self.db.flush()

            self.assertEquals(self.cluster.status, 'new')

    def test_get_task_by_uuid_returns_task(self):
        task = Task(name='deploy')
        self.db.add(task)
        self.db.flush()
        task_by_uuid = objects.Task.get_by_uuid(task.uuid)
        self.assertEquals(task.uuid, task_by_uuid.uuid)

    def test_get_task_by_uuid_raises_error(self):
        self.assertRaises(errors.ObjectNotFound,
                          objects.Task.get_by_uuid,
                          uuid='not_found_uuid',
                          fail_if_not_found=True)

    def test_task_wrong_status_filtered(self):
        task = Task(name='deploy')
        self.db.add(task)
        self.db.flush()

        task_obj = objects.Task.get_by_uuid(task.uuid)
        self.assertEquals(consts.TASK_STATUSES.running, task_obj.status)

        # Checking correct status is set
        objects.Task.update(task, {'status': consts.TASK_STATUSES.ready})
        self.db.flush()
        task_obj = objects.Task.get_by_uuid(task.uuid)
        self.assertEquals(consts.TASK_STATUSES.ready, task_obj.status)

        # Checking wrong statuses are not set
        objects.Task.update(task, {'status': None})
        self.db.flush()
        task_obj = objects.Task.get_by_uuid(task.uuid)
        self.assertEquals(consts.TASK_STATUSES.ready, task_obj.status)

        objects.Task.update(task, {'status': 'xxx'})
        self.db.flush()
        task_obj = objects.Task.get_by_uuid(task.uuid)
        self.assertEquals(consts.TASK_STATUSES.ready, task_obj.status)
