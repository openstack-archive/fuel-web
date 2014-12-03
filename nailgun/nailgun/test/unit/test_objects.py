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
import datetime
import hashlib
import jsonschema
import six
import uuid

from itertools import cycle
from itertools import ifilter

import mock

from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import BaseTestCase
from nailgun.test.base import reverse

from nailgun.errors import errors

from nailgun import consts

from nailgun.db import NoCacheQuery
from nailgun.db.sqlalchemy.models import NodeBondInterface
from nailgun.db.sqlalchemy.models import Task

from nailgun.openstack.common import jsonutils

from nailgun import objects
from nailgun.settings import settings


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
        self.assertFalse(
            objects.Cluster.should_assign_public_to_all_nodes(cluster))

        nodes_w_public_count = sum(int(objects.Node.should_have_public(node))
                                   for node in self.env.nodes)
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
        self.assertTrue(
            objects.Cluster.should_assign_public_to_all_nodes(cluster))

        nodes_w_public_count = sum(int(objects.Node.should_have_public(node))
                                   for node in self.env.nodes)
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
            "group_id",
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

    def test_reset_to_discover(self):
        self.env.create(
            nodes_kwargs=[
                {'role': 'controller'},
                {'role': 'controller'},
            ]
        )
        netmanager = objects.Cluster.get_network_manager()
        netmanager.assign_admin_ips(self.env.nodes)
        for node in self.env.nodes:
            networks = [ip.network_data.name for ip in node.ip_addrs]
            prev_roles = node.roles
            self.assertIn(consts.NETWORKS.fuelweb_admin, networks)
            objects.Node.reset_to_discover(node)
            self.db().flush()
            self.db().refresh(node)
            self.assertEqual(node.status, consts.NODE_STATUSES.discover)
            self.assertEqual(node.ip_addrs, [])
            self.assertEqual(node.pending_roles, prev_roles)


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


@mock.patch.object(settings, 'MASTER_IP', '127.0.0.1')
class TestReleaseOrchestratorData(BaseIntegrationTest):

    def setUp(self):
        super(TestReleaseOrchestratorData, self).setUp()

        self.release = self.env.create_release(api=False)

        self.data = {
            'release_id': self.release.id,
            'repo_metadata': {
                '5.1': 'http://{MASTER_IP}:8080/centos/x86_64',
                '5.1-user': 'http://{MASTER_IP}:8080/centos-user/x86_64',
            },
            'puppet_manifests_source': 'rsync://{MASTER_IP}:/puppet/modules/',
            'puppet_modules_source': 'rsync://{MASTER_IP}:/puppet/manifests/',
        }

    def test_render_data_in_create(self):
        instance = objects.ReleaseOrchestratorData.create(self.data)

        self.assertEqual(instance.repo_metadata, {
            '5.1': 'http://127.0.0.1:8080/centos/x86_64',
            '5.1-user': 'http://127.0.0.1:8080/centos-user/x86_64'})
        self.assertEqual(
            instance.puppet_manifests_source,
            'rsync://127.0.0.1:/puppet/modules/')
        self.assertEqual(
            instance.puppet_modules_source,
            'rsync://127.0.0.1:/puppet/manifests/')

    def test_render_data_in_update(self):
        instance = objects.ReleaseOrchestratorData.create(self.data)

        with mock.patch.object(settings, 'MASTER_IP', '192.168.1.1'):
            instance = \
                objects.ReleaseOrchestratorData.update(instance, self.data)

            self.assertEqual(instance.repo_metadata, {
                '5.1': 'http://192.168.1.1:8080/centos/x86_64',
                '5.1-user': 'http://192.168.1.1:8080/centos-user/x86_64'})
            self.assertEqual(
                instance.puppet_manifests_source,
                'rsync://192.168.1.1:/puppet/modules/')
            self.assertEqual(
                instance.puppet_modules_source,
                'rsync://192.168.1.1:/puppet/manifests/')

    def test_render_unmasked_data(self):
        self.data = {
            'release_id': self.release.id,
            'repo_metadata': {
                '5.1': 'http://10.20.0.2:8080/centos/x86_64',
                '5.1-user': 'http://{MASTER_IP}:8080/centos-user/x86_64',
            },
            'puppet_manifests_source': 'rsync://10.20.0.2:/puppet/modules/',
            'puppet_modules_source': 'rsync://10.20.0.2:/puppet/manifests/',
        }
        instance = objects.ReleaseOrchestratorData.create(self.data)

        self.assertEqual(instance.repo_metadata, {
            '5.1': 'http://10.20.0.2:8080/centos/x86_64',
            '5.1-user': 'http://127.0.0.1:8080/centos-user/x86_64'})
        self.assertEqual(
            instance.puppet_manifests_source,
            'rsync://10.20.0.2:/puppet/modules/')
        self.assertEqual(
            instance.puppet_modules_source,
            'rsync://10.20.0.2:/puppet/manifests/')

    def test_render_openstack_version(self):
        self.data = {
            'release_id': self.release.id,
            'repo_metadata': {
                '{OPENSTACK_VERSION}':
                'http://10.20.0.2:8080/{OPENSTACK_VERSION}/centos/x86_64',
            },
            'puppet_manifests_source': 'rsync://10.20.0.2:/puppet/modules/',
            'puppet_modules_source': 'rsync://10.20.0.2:/puppet/manifests/',
        }
        instance = objects.ReleaseOrchestratorData.create(self.data)

        self.assertEqual(instance.repo_metadata, {
            self.release.version:
            'http://10.20.0.2:8080/{0}/centos/x86_64'.format(
                self.release.version)})
        self.assertEqual(
            instance.puppet_manifests_source,
            'rsync://10.20.0.2:/puppet/modules/')
        self.assertEqual(
            instance.puppet_modules_source,
            'rsync://10.20.0.2:/puppet/manifests/')


class TestActionLogObject(BaseIntegrationTest):

    def _create_log_entry(self, object_data):
        object_data['actor_id'] = hashlib.sha256('actionlog_test').hexdigest()
        object_data['start_timestamp'] = datetime.datetime.now()
        object_data['end_timestamp'] = \
            object_data['start_timestamp'] + datetime.timedelta(hours=1)

        return objects.ActionLog.create(object_data)

    def test_validate_json_schema(self):
        object_data = {
            'action_group': 'test_group',
            'action_name': 'test_action_one',
            'action_type': 'http_request',
            'additional_info': {},
            'is_sent': False,
            'cluster_id': 1
        }

        al = self._create_log_entry(object_data)

        instance_to_validate = jsonutils.loads(objects.ActionLog.to_json(al))
        self.assertNotRaises(jsonschema.ValidationError, jsonschema.validate,
                             instance_to_validate, objects.ActionLog.schema)

    def test_validate_json_schema_failure(self):
        object_data = {
            'id': 1,
            'action_group': 'test_group',
            'action_name': 'test_action_one',
            'action_type': consts.ACTION_TYPES.http_request,
            'additional_info': '',  # validation should fail because of this
            'is_sent': False,
            'cluster_id': 1
        }

        al = self._create_log_entry(object_data)

        instance_to_validate = jsonutils.loads(objects.ActionLog.to_json(al))
        self.assertRaises(jsonschema.ValidationError, jsonschema.validate,
                          instance_to_validate, objects.ActionLog.schema)

    def test_get_by_uuid_method(self):
        object_data = {
            'id': 1,
            'action_group': 'test_group',
            'action_name': 'test_action',
            'action_type': consts.ACTION_TYPES.nailgun_task,
            'additional_info': {},
            'is_sent': False,
            'cluster_id': 1,
            'task_uuid': str(uuid.uuid4())
        }

        al = self._create_log_entry(object_data)
        self.db.add(al)
        self.db.commit()

        al_db = objects.ActionLog.get_by_task_uuid(object_data['task_uuid'])

        self.assertIsNotNone(al_db)

        self.db.delete(al)
        self.db.commit()

    def test_update_method(self):
        object_data = {
            'id': 1,
            'action_group': 'test_group',
            'action_name': 'test_action',
            'action_type': consts.ACTION_TYPES.nailgun_task,
            'additional_info': {'already_present_data': None},
            'is_sent': False,
            'cluster_id': 1,
            'task_uuid': str(uuid.uuid4())
        }

        al = self._create_log_entry(object_data)

        update_kwargs = {
            'additional_info': {'new_data': []}
        }

        al = objects.ActionLog.update(al, update_kwargs)

        self.assertIn('new_data', six.iterkeys(al.additional_info))
        self.assertIn('already_present_data', six.iterkeys(al.additional_info))

        self.db.rollback()


class TestClusterObject(BaseTestCase):

    def setUp(self):
        super(TestClusterObject, self).setUp()
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller']},
                {'roles': ['controller']},
                {'roles': ['compute']},
                {'roles': ['cinder']}])

    def test_all_controllers(self):
        self.assertEqual(len(objects.Cluster.get_all_controllers(
            self.env.clusters[0])), 2)

    def test_get_group_id(self):
        controllers = objects.Cluster.get_all_controllers(
            self.env.clusters[0])
        group_id = objects.Cluster.get_controllers_group_id(
            self.env.clusters[0])
        self.assertEqual(controllers[0].group_id, group_id)

    def test_get_nic_interfaces_for_all_nodes(self):
        nodes = self.env.nodes
        interfaces = []
        for node in nodes:
            for inf in node.nic_interfaces:
                interfaces.append(inf)
        nic_interfaces = objects.Cluster.get_nic_interfaces_for_all_nodes(
            self.env.clusters[0])
        self.assertEqual(len(nic_interfaces), len(interfaces))

    def test_get_bond_interfaces_for_all_nodes(self):
        node = self.env.nodes[0]
        node.bond_interfaces.append(
            NodeBondInterface(name='ovs-bond0',
                              slaves=node.nic_interfaces))
        self.db.flush()
        bond_interfaces = objects.Cluster.get_bond_interfaces_for_all_nodes(
            self.env.clusters[0])
        self.assertEqual(len(bond_interfaces), 1)
