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
import mock

from itertools import cycle
from itertools import ifilter
import re
import uuid

import jsonschema
from oslo_serialization import jsonutils
import six
from six.moves import range

from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import BaseTestCase
from nailgun.utils import reverse

from nailgun.errors import errors

from nailgun import consts

from nailgun.db import NoCacheQuery
from nailgun.db.sqlalchemy.models import NodeBondInterface
from nailgun.db.sqlalchemy.models import Task

from nailgun.network.manager import NetworkManager
from nailgun.network.neutron import NeutronManager
from nailgun.network.neutron import NeutronManager70

from nailgun import objects
from nailgun.plugins.manager import PluginManager


class TestObjects(BaseIntegrationTest):

    def test_filter_by(self):
        names = cycle('ABCD')
        os = cycle(['CentOS', 'Ubuntu'])
        for i in range(12):
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
        for i in range(12):
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

    @mock.patch('nailgun.objects.node.fire_callback_on_node_delete')
    def test_delete(self, callback_mock):
        cluster = self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'role': 'controller'}])
        node_db = cluster.nodes[0]
        self.assertEqual(len(cluster.nodes), 1)
        objects.Node.delete(node_db)
        callback_mock.assert_called_once_with(node_db)
        self.db.refresh(cluster)
        self.assertEqual(len(cluster.nodes), 0)

    @mock.patch(
        'nailgun.objects.node.'
        'fire_callback_on_node_collection_delete')
    def test_delete_by_ids(self, callback_mock):
        cluster = self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'role': 'controller'}] * 3)
        ids = [n.id for n in cluster.nodes]
        self.assertEqual(len(ids), 3)
        objects.NodeCollection.delete_by_ids(ids)
        callback_mock.assert_called_once_with(ids)
        self.db.refresh(cluster)
        self.assertEqual(len(cluster.nodes), 0)

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

    def test_should_have_public_with_ip(self):
        nodes = [
            {'roles': ['controller', 'cinder'], 'pending_addition': True},
            {'roles': ['compute', 'cinder'], 'pending_addition': True},
            {'roles': ['compute'], 'pending_addition': True},
            {'roles': ['mongo'], 'pending_addition': True},
            {'roles': [], 'pending_roles': ['cinder'],
             'pending_addition': True},
            {'roles': [], 'pending_roles': ['controller'],
             'pending_addition': True}]
        self.env.create(
            cluster_kwargs={
                'net_provider': 'neutron'},
            nodes_kwargs=nodes)

        cluster = self.env.clusters[0]
        cluster.release.roles_metadata['mongo']['public_ip_required'] = True
        attrs = cluster.attributes.editable
        self.assertEqual(
            attrs['public_network_assignment']['assign_to_all_nodes']['value'],
            False
        )
        self.assertFalse(
            objects.Cluster.should_assign_public_to_all_nodes(cluster))

        nodes_w_public_count = sum(
            int(objects.Node.should_have_public_with_ip(node))
            for node in self.env.nodes)
        self.assertEqual(nodes_w_public_count, 3)

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

        nodes_w_public_count = sum(
            int(objects.Node.should_have_public_with_ip(node))
            for node in self.env.nodes)
        self.assertEqual(nodes_w_public_count, len(nodes))

    def test_should_have_public(self):
        nodes = [
            {'roles': ['controller', 'cinder'], 'pending_addition': True},
            {'roles': ['compute', 'cinder'], 'pending_addition': True},
            {'roles': ['compute'], 'pending_addition': True},
            {'roles': ['mongo'], 'pending_addition': True},
            {'roles': [], 'pending_roles': ['cinder'],
             'pending_addition': True},
            {'roles': [], 'pending_roles': ['controller'],
             'pending_addition': True}]
        self.env.create(
            cluster_kwargs={
                'net_provider': 'neutron'},
            nodes_kwargs=nodes)

        cluster = self.env.clusters[0]
        attrs = cluster.attributes.editable
        attrs['neutron_advanced_configuration']['neutron_dvr']['value'] = True
        resp = self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster.id}),
            params=jsonutils.dumps({'editable': attrs}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertTrue(
            objects.Cluster.neutron_dvr_enabled(cluster))
        self.assertFalse(
            objects.Cluster.should_assign_public_to_all_nodes(cluster))

        nodes_w_public_count = sum(
            int(objects.Node.should_have_public(node))
            for node in self.env.nodes)
        # only controllers and computes should have public for DVR
        self.assertEqual(4, nodes_w_public_count)

        nodes_w_public_ip_count = sum(
            int(objects.Node.should_have_public_with_ip(node))
            for node in self.env.nodes)
        # only controllers should have public with IP address for DVR
        self.assertEqual(2, nodes_w_public_ip_count)

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
            "hostname",
            "fqdn",
            "mac",
            "meta",
            "name",
            "agent_checksum"
        ]
        fields = set(
            objects.Node.schema["properties"].keys()
        ) - set(exclude_fields)

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

    def test_make_slave_name(self):
        node = self.env.create_node()

        node.hostname = 'test-name'

        self.assertEqual(
            'test-name',
            objects.Node.get_slave_name(node))

        node.hostname = ''

        self.assertEqual(
            "node-{0}".format(node.id),
            objects.Node.get_slave_name(node))

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

    def _assert_cluster_create_data(self, network_data):
        release = self.env.create_release(api=False)
        expected_data = {
            "name": "cluster-0",
            "mode": consts.CLUSTER_MODES.ha_compact,
            "release_id": release.id,
        }
        expected_data.update(network_data)
        cluster = self.env.create_cluster(api=False, **expected_data)
        create_data = objects.Cluster.get_create_data(cluster)
        self.assertEqual(expected_data, create_data)

    def test_cluster_get_create_data_neutron(self):
        network_data = {
            "net_provider": consts.CLUSTER_NET_PROVIDERS.neutron,
            "net_segment_type": consts.NEUTRON_SEGMENT_TYPES.vlan,
            "net_l23_provider": consts.NEUTRON_L23_PROVIDERS.ovs,
        }
        self._assert_cluster_create_data(network_data)

    def test_cluster_get_create_data_nova(self):
        network_data = {
            "net_provider": consts.CLUSTER_NET_PROVIDERS.nova_network,
        }
        self._assert_cluster_create_data(network_data)


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

    def test_update_vms_conf(self):
        kvm_node = self.cluster.nodes[0]
        kvm_node.roles = [consts.VIRTUAL_NODE_TYPES.virt]
        self.db.flush()
        objects.Node.set_vms_conf(kvm_node,
                                  [{'id': 1, 'cluster_id': self.cluster.id}])
        task = Task(name=consts.TASK_NAMES.spawn_vms,
                    cluster=self.cluster, status='ready')
        self.db.add(task)
        self.db.flush()

        objects.Task._update_cluster_data(task)
        self.db.flush()

        for node in self.cluster.nodes:
            if consts.VIRTUAL_NODE_TYPES.virt in node.roles:
                self.assertTrue(node.attributes.vms_conf[0].get('created'))
            else:
                self.assertNotEquals(node.status, 'ready')

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

        al_db = objects.ActionLog.get_by_kwargs(
            task_uuid=object_data['task_uuid'])

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

    def _create_cluster_with_plugins(self, plugins_kw_list):
        cluster = self.env.create_cluster(api=False)

        for kw in plugins_kw_list:
            cluster.plugins.append(objects.Plugin.create(kw))

        return cluster

    def _get_network_role_metadata(self, **kwargs):
        network_role = {
            'id': 'test_network_role',
            'default_mapping': 'public',
            'properties': {
                'subnet': True,
                'gateway': False,
                'vip': [
                    {'name': 'test_vip_a'}
                ]
            }
        }
        network_role.update(kwargs)
        return network_role

    @mock.patch('nailgun.objects.cluster.fire_callback_on_cluster_delete')
    @mock.patch(
        'nailgun.objects.cluster.'
        'fire_callback_on_node_collection_delete')
    def test_delete(self, mock_node_coll_delete_cb, mock_cluster_delete_cb):
        cluster = self.env.clusters[0]
        ids = [node.id for node in cluster.nodes]
        objects.Cluster.delete(cluster)
        mock_node_coll_delete_cb.assert_called_once_with(ids)
        mock_cluster_delete_cb.assert_called_once_with(cluster)
        self.assertEqual(self.db.query(objects.Node.model).count(), 0)
        self.assertEqual(self.db.query(objects.Cluster.model).count(), 0)

    def test_all_controllers(self):
        self.assertEqual(len(objects.Cluster.get_nodes_by_role(
            self.env.clusters[0], 'controller')), 2)

    def test_get_group_id(self):
        controllers = objects.Cluster.get_nodes_by_role(
            self.env.clusters[0], 'controller')
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

    def test_get_network_roles(self):
        cluster = self.env.clusters[0]
        self.assertEqual(
            objects.Cluster.get_network_roles(cluster),
            cluster.release.network_roles_metadata)

    def test_get_deployment_tasks(self):
        deployment_tasks = self.env.get_default_plugin_deployment_tasks()
        plugin_metadata = self.env.get_default_plugin_metadata(
            deployment_tasks=deployment_tasks
        )

        cluster = self._create_cluster_with_plugins([plugin_metadata])

        cluster_deployment_tasks = \
            objects.Cluster.get_deployment_tasks(cluster)

        tasks_ids = [t['id'] for t in cluster_deployment_tasks]
        depl_task_id = deployment_tasks[0]['id']
        self.assertIn(depl_task_id, tasks_ids)

        default_tasks_count = len(cluster.release.deployment_tasks)
        self.assertEqual(len(cluster_deployment_tasks),
                         default_tasks_count +
                         len(cluster.plugins[0].deployment_tasks))

    def test_get_deployment_tasks_overlapping_error(self):
        deployment_tasks = self.env.get_default_plugin_deployment_tasks()
        plugins_kw_list = [
            self.env.get_default_plugin_metadata(
                name=plugin_name,
                deployment_tasks=deployment_tasks)
            for plugin_name in ('test_plugin_first', 'test_plugin_second')
        ]

        cluster = self._create_cluster_with_plugins(plugins_kw_list)

        expected_message = (
            'Plugin test_plugin_second-0.1.0 is overlapping with plugin '
            'test_plugin_first-0.1.0 by introducing the same '
            'deployment task with id role-name'
        )
        with self.assertRaisesRegexp(errors.AlreadyExists,
                                     expected_message):
            objects.Cluster.get_deployment_tasks(cluster)

    def test_get_plugin_network_roles(self):
        network_roles = [self._get_network_role_metadata()]
        plugin_data = self.env.get_default_plugin_metadata(
            network_roles_metadata=network_roles)
        cluster = self._create_cluster_with_plugins([plugin_data])
        self.assertItemsEqual(
            objects.Cluster.get_network_roles(cluster),
            cluster.release.network_roles_metadata + network_roles)

    def test_get_plugin_network_roles_fail(self):
        network_roles = [self._get_network_role_metadata()]
        plugins_kw_list = [
            self.env.get_default_plugin_metadata(
                name=plugin_name,
                network_roles_metadata=network_roles)
            for plugin_name in ('test_plugin_first', 'test_plugin_second')
        ]

        cluster = self._create_cluster_with_plugins(plugins_kw_list)
        self.assertRaises(
            errors.NetworkRoleConflict,
            objects.Cluster.get_network_roles, cluster)

    def test_get_volumes_metadata_when_plugins_are_enabled(self):
        plugin_volumes_metadata = {
            'volumes_roles_mapping': {
                'test_plugin_1': [
                    {'allocate_size': 'min', 'id': 'test_plugin_1'}
                ],
                'test_plugin_2': [
                    {'allocate_size': 'min', 'id': 'test_plugin_2'}
                ],
            },
            'volumes': [
                {'id': 'test_plugin_1', 'type': 'vg'},
                {'id': 'test_plugin_2', 'type': 'vg'}
            ]
        }
        with mock.patch.object(
                PluginManager, 'get_volumes_metadata') as plugin_volumes:
            plugin_volumes.return_value = plugin_volumes_metadata
            expected_volumes_metadata = copy.deepcopy(
                self.env.releases[0].volumes_metadata)
            expected_volumes_metadata['volumes_roles_mapping'].update(
                plugin_volumes_metadata['volumes_roles_mapping'])
            expected_volumes_metadata['volumes'].extend(
                plugin_volumes_metadata['volumes'])

            volumes_metadata = objects.Cluster.get_volumes_metadata(
                self.env.clusters[0])

            self.assertDictEqual(
                volumes_metadata, expected_volumes_metadata)


class TestClusterObjectGetRoles(BaseTestCase):

    def setUp(self):
        super(TestClusterObjectGetRoles, self).setUp()

        self.env.create(
            release_kwargs={
                'roles_metadata': {
                    'role_a': {
                        'name': 'Role A', 'description': 'Role A is ...', },
                    'role_b': {
                        'name': 'Role B', 'description': 'Role B is ...', },
                }
            })
        self.cluster = self.env.clusters[0]

    def create_plugin(self, roles_metadata):
        plugin = objects.Plugin.create(self.env.get_default_plugin_metadata(
            name=uuid.uuid4().get_hex(),
            roles_metadata=roles_metadata,
        ))
        self.cluster.plugins.append(plugin)
        self.db.flush()

        return plugin

    def test_no_plugins_no_additional_roles(self):
        roles = objects.Cluster.get_roles(self.cluster)
        self.assertEqual(roles, {
            'role_a': {
                'name': 'Role A', 'description': 'Role A is ...', },
            'role_b': {
                'name': 'Role B', 'description': 'Role B is ...', },
        })

    def test_plugin_adds_new_roles(self):
        self.create_plugin({
            'role_c': {
                'name': 'Role C', 'description': 'Role C is ...', },
        })

        roles = objects.Cluster.get_roles(self.cluster)
        self.assertEqual(roles, {
            'role_a': {
                'name': 'Role A', 'description': 'Role A is ...', },
            'role_b': {
                'name': 'Role B', 'description': 'Role B is ...', },
            'role_c': {
                'name': 'Role C', 'description': 'Role C is ...', },
        })

    def test_plugin_role_conflict_with_core_roles(self):
        plugin = self.create_plugin({
            'role_a': {
                'name': 'Role X', 'description': 'Role X is ...', },
        })

        expected_message = (
            "Plugin \(ID={0}\) is unable to register "
            "the following node roles: role_a"
            .format(plugin.id)
        )
        with self.assertRaisesRegexp(errors.AlreadyExists,
                                     expected_message):
            objects.Cluster.get_roles(self.cluster)

    def test_plugin_role_conflict_with_other_plugins(self):
        self.create_plugin({
            'role_x': {
                'name': 'Role X', 'description': 'Role X is ...', },
        })
        plugin_in_conflict = self.create_plugin({
            'role_x': {
                'name': 'Role X', 'description': 'Role X is ...', },
        })
        expected_message = (
            "Plugin \(ID={0}\) is unable to register "
            "the following node roles: role_x"
            .format(plugin_in_conflict.id)
        )
        with self.assertRaisesRegexp(errors.AlreadyExists,
                                     expected_message):
            objects.Cluster.get_roles(self.cluster)

    def test_plugin_role_conflict_with_plugin_and_core(self):
        self.create_plugin({
            'role_x': {
                'name': 'Role X', 'description': 'Role X is ...', },
        })
        plugin_in_conflict = self.create_plugin({
            'role_x': {
                'name': 'Role Y', 'description': 'Role Y is ...', },
            'role_a': {
                'name': 'Role A', 'description': 'Role A is ...', },
        })

        message_pattern = (
            '^Plugin \(ID={0}\) is unable to register the following node '
            'roles: (.*)'
            .format(plugin_in_conflict.id))

        with self.assertRaisesRegexp(
                errors.AlreadyExists, message_pattern) as cm:
            objects.Cluster.get_roles(self.cluster)

        # 0 - the whole message, 1 - is first match of (.*) pattern
        roles = re.match(message_pattern, str(cm.exception)).group(1)
        roles = set([role.lstrip().rstrip() for role in roles.split(',')])

        self.assertEqual(roles, set(['role_x', 'role_a']))


class TestClusterObjectGetNetworkManager(BaseTestCase):
    def setUp(self):
        super(TestClusterObjectGetNetworkManager, self).setUp()
        self.env.create(cluster_kwargs={'net_provider': 'neutron'})

    def test_get_default(self):
        nm = objects.Cluster.get_network_manager()
        self.assertEqual(nm, NetworkManager)

    def test_get_neutron(self):
        nm = objects.Cluster.get_network_manager(self.env.clusters[0])
        self.assertEqual(nm, NeutronManager)

    def test_get_neutron_70(self):
        self.env.clusters[0].release.version = '2014.2.2-7.0'
        nm = objects.Cluster.get_network_manager(self.env.clusters[0])
        self.assertEqual(nm, NeutronManager70)
