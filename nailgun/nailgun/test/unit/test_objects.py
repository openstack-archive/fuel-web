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
import uuid

from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy.orm import Query

import jsonschema
from oslo_serialization import jsonutils
import six
from six.moves import range

from nailgun.api.v1.validators.json_schema import action_log

from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import BaseTestCase
from nailgun.utils import reverse

from nailgun.errors import errors

from nailgun import consts

from nailgun.db.sqlalchemy.models import IPAddr
from nailgun.db.sqlalchemy.models import NodeBondInterface
from nailgun.db.sqlalchemy.models import NodeGroup
from nailgun.db.sqlalchemy.models import Task

from nailgun.network.manager import NetworkManager
from nailgun.network.neutron import NeutronManager61
from nailgun.network.neutron import NeutronManager70
from nailgun.network.neutron import NeutronManager80
from nailgun.network.neutron import NeutronManagerLegacy
from nailgun.network.nova_network import NovaNetworkManager61
from nailgun.network.nova_network import NovaNetworkManager70
from nailgun.network.nova_network import NovaNetworkManagerLegacy


from nailgun import objects
from nailgun.plugins.manager import PluginManager
from nailgun.test import base
from nailgun.utils import dict_merge


class TestObjects(BaseIntegrationTest):

    def test_filter_by(self):
        names = cycle('ABCD')
        os = cycle([consts.RELEASE_OS.centos, consts.RELEASE_OS.ubuntu])
        for i in range(12):
            self.env.create_release(
                name=names.next(),
                operating_system=os.next()
            )

        # filtering query - returns query
        query_filtered = objects.ReleaseCollection.filter_by(
            objects.ReleaseCollection.all(),
            name="A",
            operating_system=consts.RELEASE_OS.centos
        )
        self.assertIsInstance(query_filtered, Query)
        self.assertEqual(
            objects.ReleaseCollection.count(query_filtered),
            3
        )
        for r in query_filtered:
            self.assertEqual(r.name, "A")
            self.assertEqual(r.operating_system, consts.RELEASE_OS.centos)

        # filtering iterable - returns ifilter
        iterable_filtered = objects.ReleaseCollection.filter_by(
            list(objects.ReleaseCollection.all()),
            name="A",
            operating_system=consts.RELEASE_OS.centos
        )
        self.assertIsInstance(iterable_filtered, ifilter)
        self.assertEqual(
            objects.ReleaseCollection.count(iterable_filtered),
            3
        )
        for r in iterable_filtered:
            self.assertEqual(r.name, "A")
            self.assertEqual(r.operating_system, consts.RELEASE_OS.centos)

        iterable_filtered = objects.ReleaseCollection.filter_by(
            list(),
            name="A",
        )
        self.assertIsInstance(iterable_filtered, ifilter)
        self.assertEquals(0, len(list(iterable_filtered)))

    def test_filter_by_not(self):
        names = cycle('ABCDE')
        os = cycle([consts.RELEASE_OS.centos, consts.RELEASE_OS.ubuntu])

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
            operating_system=consts.RELEASE_OS.centos
        )
        self.assertIsInstance(query_filtered, Query)
        self.assertEqual(
            objects.ReleaseCollection.count(query_filtered),
            10
        )
        for r in query_filtered:
            if r.name == "A":
                self.assertNotEqual(r.operating_system,
                                    consts.RELEASE_OS.centos)
            elif r.operating_system == consts.RELEASE_OS.centos:
                self.assertNotEqual(r.name, "A")

        # filtering iterable - returns ifilter
        iterable_filtered = objects.ReleaseCollection.filter_by_not(
            list(objects.ReleaseCollection.all()),
            name="A",
            operating_system=consts.RELEASE_OS.centos
        )
        self.assertIsInstance(iterable_filtered, ifilter)
        self.assertEqual(
            objects.ReleaseCollection.count(iterable_filtered),
            10
        )
        for r in iterable_filtered:
            if r.name == "A":
                self.assertNotEqual(r.operating_system,
                                    consts.RELEASE_OS.centos)
            elif r.operating_system == consts.RELEASE_OS.centos:
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

    def test_update_cluster_assignment(self):
        cluster = self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'role': 'controller'}] * 3)
        new_cluster = self.env.create_cluster(api=False)
        new_group = objects.Cluster.get_default_group(new_cluster)
        node = cluster.nodes[0]
        roles = node.roles
        objects.Node.update_cluster_assignment(node, new_cluster)
        self.assertEqual(new_cluster.id, node.cluster_id)
        self.assertEqual(new_group.id, node.group_id)
        self.assertEqual([], node.roles)
        self.assertItemsEqual(roles, node.pending_roles)
        self.assertEqual(node.attributes, cluster.release.node_attributes)

    def test_update_cluster_assignment_with_templates_80(self):
        cluster = self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'role': 'controller'}] * 3)
        new_cluster = self.env.create(
            cluster_kwargs={'api': False},
            release_kwargs={'version': 'liberty-8.0'},
        )

        net_template = self.env.read_fixtures(['network_template_80'])[0]
        objects.Cluster.set_network_template(new_cluster, net_template)

        new_group = objects.Cluster.get_default_group(new_cluster)
        node = cluster.nodes[0]
        roles = node.roles
        objects.Node.update_cluster_assignment(node, new_cluster)
        self.assertEqual(new_cluster.id, node.cluster_id)
        self.assertEqual(new_group.id, node.group_id)
        self.assertEqual([], node.roles)
        self.assertItemsEqual(roles, node.pending_roles)
        self.assertIsNotNone(node.network_template)
        endpoints = node.network_template['templates']['common']['endpoints']
        self.assertEqual([u'br-mgmt', u'br-fw-admin'], endpoints)

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
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
            },
            nodes_kwargs=nodes)

        cluster = self.env.clusters[0]
        cluster.release.roles_metadata['mongo']['public_ip_required'] = True
        attrs = cluster.attributes.editable
        self.assertFalse(
            attrs['public_network_assignment']['assign_to_all_nodes']['value'])
        self.assertFalse(
            objects.Cluster.should_assign_public_to_all_nodes(cluster))

        nodes_w_public_count = sum(
            int(objects.Node.should_have_public_with_ip(node))
            for node in self.env.nodes)
        self.assertEqual(nodes_w_public_count, 3)

        attrs['public_network_assignment']['assign_to_all_nodes']['value'] = \
            True

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
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
            },
            nodes_kwargs=nodes)

        cluster = self.env.clusters[0]
        attrs = copy.deepcopy(cluster.attributes.editable)
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
        cluster = self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"role": "controller"}
            ]
        )
        node_db = self.env.nodes[0]
        config = self.env.create_openstack_config(
            cluster_id=cluster['id'], node_id=node_db.id, configuration={})

        node2_db = self.env.create_node()
        objects.Node.remove_from_cluster(node_db)
        self.db().refresh(config)
        self.assertEqual(node_db.cluster_id, None)
        self.assertEqual(node_db.roles, [])
        self.assertEqual(node_db.pending_roles, [])
        self.assertFalse(config.is_active)
        self.assertEqual(node_db.attributes, {})

        exclude_fields = [
            "group_id",
            "id",
            "hostname",
            "fqdn",
            "mac",
            "meta",
            "name",
            "agent_checksum",
            "uuid",
            "timestamp",
            "nic_interfaces",
            "attributes",
        ]
        fields = set(
            c.key for c in sqlalchemy_inspect(objects.Node.model).attrs
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
        for status in (consts.NODE_STATUSES.provisioning,
                       consts.NODE_STATUSES.error):
            node_db.status = status
            data["status"] = consts.NODE_STATUSES.discover
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
        ordered_nodes = objects.NodeCollection.order_by(nodes, ('role', '-id'))
        self.assertListEqual(
            ordered_nodes,
            [self.env.nodes[i] for i in [1, 2, 7, 6, 5, 4, 3, 0]]
        )

    def test_eager_nodes_handlers(self):
        """Custom handler works and returns correct number of nodes."""
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

    def test_apply_network_template(self):
        node = self.env.create_node()
        template = self.env.read_fixtures(['network_template_80'])[0]

        group_name = 'group-custom-1'
        with mock.patch('objects.NodeGroup.get_by_uid',
                        return_value=NodeGroup(name=group_name)):
            objects.Node.apply_network_template(node, template)
            self.assertDictEqual(
                node.network_template['templates'],
                base.get_nodegroup_network_schema_template(
                    template, group_name)
            )

    def test_update_w_error(self):
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller']},
                {'roles': ['compute', 'cinder']}
            ]
        )
        cluster_2 = self.env.create_cluster()

        node_0 = self.env.nodes[0]
        data = {
            'cluster_id': cluster_2['id']
        }

        self.assertRaises(
            errors.CannotUpdate, objects.Node.update, node_0, data)


class TestTaskObject(BaseIntegrationTest):

    def setUp(self):
        super(TestTaskObject, self).setUp()
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller']},
                {'roles': ['compute']},
                {'roles': ['cinder']}])

    def _node_should_be_error_with_type(self, node, error_type):
        self.assertEquals(node.status, consts.NODE_STATUSES.error)
        self.assertEquals(node.error_type, error_type)
        self.assertEquals(node.progress, 0)

    def _nodes_should_not_be_error(self, nodes):
        for node in nodes:
            self.assertEquals(node.status, consts.NODE_STATUSES.discover)

    @property
    def cluster(self):
        return self.env.clusters[0]

    def test_update_nodes_to_error_if_deployment_task_failed(self):
        self.cluster.nodes[0].status = consts.NODE_STATUSES.deploying
        self.cluster.nodes[0].progress = 12
        task = Task(name=consts.TASK_NAMES.deployment,
                    cluster=self.cluster,
                    status=consts.TASK_STATUSES.error)
        self.db.add(task)
        self.db.flush()

        objects.Task._update_cluster_data(task)
        self.db.flush()

        self.assertEquals(self.cluster.status, consts.CLUSTER_STATUSES.error)
        self._node_should_be_error_with_type(self.cluster.nodes[0],
                                             consts.NODE_ERRORS.deploy)
        self._nodes_should_not_be_error(self.cluster.nodes[1:])

    def test_update_cluster_to_error_if_deploy_task_failed(self):
        task = Task(name=consts.TASK_NAMES.deploy,
                    cluster=self.cluster,
                    status=consts.TASK_STATUSES.error)
        self.db.add(task)
        self.db.flush()

        objects.Task._update_cluster_data(task)
        self.db.flush()

        self.assertEquals(self.cluster.status, consts.CLUSTER_STATUSES.error)

    def test_update_nodes_to_error_if_provision_task_failed(self):
        self.cluster.nodes[0].status = consts.NODE_STATUSES.provisioning
        self.cluster.nodes[0].progress = 12
        task = Task(name=consts.TASK_NAMES.provision,
                    cluster=self.cluster,
                    status=consts.TASK_STATUSES.error)
        self.db.add(task)
        self.db.flush()

        objects.Task._update_cluster_data(task)
        self.db.flush()

        self.assertEquals(self.cluster.status, consts.CLUSTER_STATUSES.error)
        self._node_should_be_error_with_type(self.cluster.nodes[0],
                                             consts.NODE_ERRORS.provision)
        self._nodes_should_not_be_error(self.cluster.nodes[1:])

    def test_update_cluster_to_operational(self):
        task = Task(name=consts.TASK_NAMES.deploy,
                    cluster=self.cluster,
                    status=consts.TASK_STATUSES.ready)
        self.db.add(task)
        self.db.flush()

        objects.Task._update_cluster_data(task)
        self.db.flush()

        self.assertEqual(self.cluster.status,
                         consts.CLUSTER_STATUSES.operational)
        self.assertTrue(
            self.cluster.attributes.generated['deployed_before']['value'])

    def test_update_vms_conf(self):
        kvm_node = self.cluster.nodes[0]
        kvm_node.roles = [consts.VIRTUAL_NODE_TYPES.virt]
        self.db.flush()
        kvm_node.vms_conf = [{'id': 1, 'cluster_id': self.cluster.id}]
        task = Task(name=consts.TASK_NAMES.spawn_vms,
                    cluster=self.cluster,
                    status=consts.TASK_STATUSES.ready)
        self.db.add(task)
        self.db.flush()

        objects.Task._update_cluster_data(task)
        self.db.flush()

        for node in self.cluster.nodes:
            if consts.VIRTUAL_NODE_TYPES.virt in node.roles:
                self.assertTrue(node.vms_conf[0].get('created'))
            else:
                self.assertNotEquals(node.status, consts.NODE_STATUSES.ready)

    def test_update_if_parent_task_is_ready_all_nodes_should_be_ready(self):
        for node in self.cluster.nodes:
            node.status = consts.NODE_STATUSES.ready
            node.progress = 100

        self.cluster.nodes[0].status = consts.NODE_STATUSES.deploying
        self.cluster.nodes[0].progress = 24

        task = Task(name=consts.TASK_NAMES.deploy,
                    cluster=self.cluster,
                    status=consts.TASK_STATUSES.ready)
        self.db.add(task)
        self.db.flush()

        objects.Task._update_cluster_data(task)
        self.db.flush()

        self.assertEquals(self.cluster.status,
                          consts.CLUSTER_STATUSES.operational)

        for node in self.cluster.nodes:
            self.assertEquals(node.status, consts.NODE_STATUSES.ready)
            self.assertEquals(node.progress, 100)

    def test_update_cluster_status_if_task_was_already_in_error_status(self):
        for node in self.cluster.nodes:
            node.status = consts.NODE_STATUSES.provisioning
            node.progress = 12

        task = Task(name=consts.TASK_NAMES.provision,
                    cluster=self.cluster,
                    status=consts.TASK_STATUSES.error)
        self.db.add(task)
        self.db.flush()

        data = {'status': consts.TASK_STATUSES.error, 'progress': 100}

        objects.Task.update(task, data)
        self.db.flush()

        self.assertEquals(self.cluster.status, consts.CLUSTER_STATUSES.error)
        self.assertEquals(task.status, consts.TASK_STATUSES.error)

        for node in self.cluster.nodes:
            self.assertEquals(node.status, consts.NODE_STATUSES.error)
            self.assertEquals(node.progress, 0)

    def test_do_not_set_cluster_to_error_if_validation_failed(self):
        for task_name in [consts.TASK_NAMES.check_before_deployment,
                          consts.TASK_NAMES.check_networks]:
            supertask = Task(
                name=consts.TASK_NAMES.deploy,
                cluster=self.cluster,
                status=consts.TASK_STATUSES.error)

            check_task = Task(
                name=task_name,
                cluster=self.cluster,
                status=consts.TASK_STATUSES.error)

            supertask.subtasks.append(check_task)
            self.db.add(check_task)
            self.db.flush()

            objects.Task._update_cluster_data(supertask)
            self.db.flush()

            self.assertEquals(self.cluster.status, consts.CLUSTER_STATUSES.new)

    def test_get_task_by_uuid_returns_task(self):
        task = Task(name=consts.TASK_NAMES.deploy)
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
        task = Task(name=consts.TASK_NAMES.deploy)
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
                             instance_to_validate, action_log.schema)

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
        self.assertRaises(jsonschema.ValidationError, jsonschema.validate,
                          object_data, action_log.schema)
        self.assertRaises(ValueError, self._create_log_entry, object_data)

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
            cluster_kwargs={'net_provider': 'neutron'},
            nodes_kwargs=[
                {'roles': ['controller']},
                {'roles': ['controller']},
                {'roles': ['compute']},
                {'roles': ['cinder']}])
        self.cluster = self.env.clusters[0]

    def _create_cluster_with_plugins(self, plugins_kw_list):
        cluster = self.env.create_cluster(api=False)

        for kw in plugins_kw_list:
            plugin = objects.Plugin.create(kw)
            cluster.plugins.append(plugin)
            objects.ClusterPlugins.set_attributes(cluster.id,
                                                  plugin.id,
                                                  enabled=True)
        return cluster

    def _get_network_role_metadata(self, **kwargs):
        network_role = {
            'id': 'test_network_role',
            'default_mapping': consts.NETWORKS.public,
            'properties': {
                'subnet': True,
                'gateway': False,
                'vip': [
                    {'name': 'test_vip_a'}
                ]
            }
        }

        return dict_merge(network_role, kwargs)

    def test_create_cluster_triggers_vips_allocation(self):
        vips = objects.IPAddrCollection.get_vips_by_cluster_id(
            self.cluster.id
        ).all()

        self.assertIsNotNone(vips)

    @mock.patch('nailgun.objects.cluster.PluginManager.'
                'enable_plugins_by_components')
    @mock.patch('nailgun.objects.cluster.ClusterPlugins')
    def test_create_cluster_vips_allocation_considers_plugins_vips(
            self, *_):
        network_roles = [self._get_network_role_metadata()]
        plugin_data = self.env.get_default_plugin_metadata(
            network_roles_metadata=network_roles)
        plugin = objects.Plugin.create(plugin_data)

        with mock.patch('nailgun.plugins.manager.ClusterPlugins') as cp_mock:
            cp_mock.get_enabled = mock.Mock(return_value=[plugin])

            cluster = self.env.create(
                release_kwargs={'version': '1111-8.0'},
                cluster_kwargs={'api': False}
            )

        plugin_vip = objects.IPAddrCollection.get_vips_by_cluster_id(
            cluster.id
        ).filter(IPAddr.vip_name == 'test_vip_a').first()

        self.assertIsNotNone(plugin_vip)

    @mock.patch('nailgun.objects.Cluster.update_nodes')
    @mock.patch('nailgun.objects.Cluster.add_pending_changes')
    @mock.patch('nailgun.objects.Cluster.get_network_manager')
    def test_create_cluster_fail_if_vips_cannot_be_allocated(self,
                                                             get_nm_mock,
                                                             *_):
        expected_errors = [
            errors.CanNotFindCommonNodeGroup,
            errors.CanNotFindNetworkForNodeGroup,
            errors.DuplicatedVIPNames,
        ]
        for exc in expected_errors:
            net_manager_mock = mock.Mock(
                assign_vips_for_net_groups=mock.Mock(side_effect=exc)
            )
            get_nm_mock.return_value = net_manager_mock

            self.assertRaises(
                errors.CannotCreate,
                objects.Cluster.create,
                {'name': uuid.uuid4().hex,
                 'release_id': self.env.releases[0].id}
            )

    # FIXME(aroma): remove this test when stop action will be reworked for ha
    # cluster. To get more details, please, refer to [1]
    # [1]: https://bugs.launchpad.net/fuel/+bug/1529691
    def test_set_deployed_before_flag(self):
        self.assertFalse(
            self.cluster.attributes.generated['deployed_before']['value'])

        # check that the flags is set to true if was false
        objects.Cluster.set_deployed_before_flag(self.cluster, value=True)
        self.assertTrue(
            self.cluster.attributes.generated['deployed_before']['value'])

        # check that flag is set to false if was true
        objects.Cluster.set_deployed_before_flag(self.cluster, value=False)
        self.assertFalse(
            self.cluster.attributes.generated['deployed_before']['value'])

        # check that flag is not changed when same value is given
        # and interaction w/ db is not performed
        with mock.patch.object(self.db, 'flush') as m_flush:
            objects.Cluster.set_deployed_before_flag(self.cluster,
                                                     value=False)
            self.assertFalse(
                self.cluster.attributes.generated['deployed_before']['value'])

            m_flush.assert_not_called()

    def test_network_defaults(self):
        cluster = objects.Cluster.get_by_uid(self.env.create(api=True)['id'])

        self.assertEqual(
            consts.CLUSTER_NET_PROVIDERS.neutron,
            cluster.net_provider)
        self.assertEqual(
            consts.NEUTRON_SEGMENT_TYPES.vlan,
            cluster.network_config.segmentation_type)

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

    def test_put_delete_template_after_deployment(self):
        allowed = [consts.CLUSTER_STATUSES.new,
                   consts.CLUSTER_STATUSES.stopped,
                   consts.CLUSTER_STATUSES.operational,
                   consts.CLUSTER_STATUSES.error]
        for status in consts.CLUSTER_STATUSES:
            self.env.clusters[0].status = status
            self.db.flush()
            self.assertEqual(
                objects.Cluster.is_network_modification_locked(
                    self.env.clusters[0]),
                status not in allowed
            )

    def test_get_controller_group_id(self):
        controllers = objects.Cluster.get_nodes_by_role(
            self.env.clusters[0], 'controller')
        group_id = objects.Cluster.get_controllers_group_id(
            self.env.clusters[0])
        self.assertEqual(controllers[0].group_id, group_id)

    def test_get_node_group(self):
        controller = objects.Cluster.get_nodes_by_role(
            self.cluster, 'controller')[0]
        compute = objects.Cluster.get_nodes_by_role(
            self.cluster, 'compute')[0]

        group_id = self.env.create_node_group().json_body['id']
        compute.group_id = group_id
        self.db.flush()

        self.assertEqual(
            group_id,
            objects.Cluster.get_common_node_group(self.cluster,
                                                  ['compute']).id)
        self.assertEqual(
            controller.group_id,
            objects.Cluster.get_common_node_group(self.cluster,
                                                  ['controller']).id)

    def test_get_node_group_multiple_return_same_group(self):
        group_id = self.env.create_node_group().json_body['id']

        compute = objects.Cluster.get_nodes_by_role(self.cluster, 'compute')[0]
        cinder = objects.Cluster.get_nodes_by_role(self.cluster, 'cinder')[0]

        compute.group_id = group_id
        cinder.group_id = group_id
        self.db.flush()

        self.assertEqual(
            group_id,
            objects.Cluster.get_common_node_group(
                self.cluster, ['compute', 'cinder']).id)

    def test_get_node_group_multiple_fail(self):
        group_id = self.env.create_node_group().json_body['id']

        controller = \
            objects.Cluster.get_nodes_by_role(self.cluster, 'controller')[0]
        cinder = objects.Cluster.get_nodes_by_role(self.cluster, 'cinder')[0]

        controller.group_id = group_id
        cinder.group_id = group_id
        self.db.flush()

        # since we have two controllers, and one of them is in another
        # node group, the error will be raised
        self.assertRaisesRegexp(
            errors.CanNotFindCommonNodeGroup,
            '^Node roles \[controller, cinder\] has more than one common '
            'node group$',
            objects.Cluster.get_common_node_group,
            self.cluster,
            ['controller', 'cinder'])

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
        self.assertItemsEqual(
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

    def test_get_refreshable_tasks(self):
        deployment_tasks = [
            self.env.get_default_plugin_deployment_tasks(**{
                'id': 'refreshable_task_on_keystone',
                consts.TASK_REFRESH_FIELD: ['keystone_config']
            })[0],
            self.env.get_default_plugin_deployment_tasks(**{
                'id': 'refreshable_task_on_nova',
                consts.TASK_REFRESH_FIELD: ['nova_config']
            })[0],
        ]
        plugin_metadata = self.env.get_default_plugin_metadata(
            deployment_tasks=deployment_tasks
        )

        cluster = self._create_cluster_with_plugins([plugin_metadata])

        refreshable_tasks = \
            objects.Cluster.get_refreshable_tasks(cluster)

        tasks_ids = [t['id'] for t in refreshable_tasks]
        self.assertIn(deployment_tasks[1]['id'], tasks_ids)
        self.assertIn(deployment_tasks[0]['id'], tasks_ids)

        refreshable_tasks_on_nova = \
            objects.Cluster.get_refreshable_tasks(
                cluster, filter_by_configs=('nova_config',))
        tasks_ids = [t['id'] for t in refreshable_tasks_on_nova]
        self.assertIn(deployment_tasks[1]['id'], tasks_ids)
        self.assertNotIn(deployment_tasks[0]['id'], tasks_ids)

    def test_get_plugin_network_roles(self):
        network_roles = [self._get_network_role_metadata()]
        plugin_data = self.env.get_default_plugin_metadata(
            network_roles_metadata=network_roles)
        cluster = self._create_cluster_with_plugins([plugin_data])
        self.assertItemsEqual(
            objects.Cluster.get_network_roles(cluster),
            cluster.release.network_roles_metadata + network_roles)

    def test_get_plugin_network_roles_fail(self):
        plugins_kw_list = [
            self.env.get_default_plugin_metadata(
                name='test_plugin_{0}'.format(idx),
                network_roles_metadata=[
                    self._get_network_role_metadata(
                        properties={'gateway': bool(idx)}
                    )
                ]
            ) for idx in six.moves.range(2)
        ]

        cluster = self._create_cluster_with_plugins(plugins_kw_list)
        self.assertRaises(
            errors.NetworkRoleConflict,
            objects.Cluster.get_network_roles, cluster)

    def test_merge_network_roles(self):
        network_roles = [self._get_network_role_metadata()]
        plugins_kw_list = [
            self.env.get_default_plugin_metadata(
                name=plugin_name,
                network_roles_metadata=network_roles)
            for plugin_name in ('test_plugin_first', 'test_plugin_second')
        ]

        cluster = self._create_cluster_with_plugins(plugins_kw_list)
        self.assertItemsEqual(
            cluster.release.network_roles_metadata + network_roles,
            objects.Cluster.get_network_roles(cluster)
        )

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

    def test_cluster_is_component_enabled(self):
        cluster = self.env.clusters[0]
        self.assertFalse(objects.Cluster.is_component_enabled(cluster,
                                                              'ironic'))
        self.env._set_additional_component(cluster, 'ironic', True)
        self.assertTrue(objects.Cluster.is_component_enabled(cluster,
                                                             'ironic'))

    def test_get_cluster_attributes_by_components(self):
        release = self.env.create_release(
            components_metadata=[{
                'name': 'hypervisor:libvirt:test',
                'bind': [['settings:common.libvirt_type.value', 'test'],
                         ['wrong_model:field.value', 'smth']]
            }, {
                'name': 'additional_service:new',
                'bind': ['settings:additional_components.new.value']
            }, {
                'name': 'network:some_net',
                'bind': [['cluster:net_provider', 'test_provider'],
                         'settings:some_net.checkbox']
            }]
        )
        selected_components = ['network:some_net', 'hypervisor:libvirt:test',
                               'additional_service:new_plugin_service']
        result_attrs = objects.Cluster.get_cluster_attributes_by_components(
            selected_components, release.id)
        self.assertDictEqual(
            result_attrs,
            {'editable': {u'some_net': {u'checkbox': True},
                          u'common': {u'libvirt_type': {u'value': u'test'}}},
             'cluster': {u'net_provider': u'test_provider'}}
        )

    def test_cluster_has_compute_vmware_changes(self):
        cluster = self.env.create_cluster(api=False)
        ready_compute_vmware_node = self.env.create_node(
            cluster_id=cluster.id,
            roles=['compute-vmware'],
            status=consts.NODE_STATUSES.ready
        )
        self.env.create_node(cluster_id=cluster.id, pending_addition=True,
                             pending_roles=['controller'])
        self.assertFalse(objects.Cluster.has_compute_vmware_changes(cluster))

        pending_compute_vmware_node = self.env.create_node(
            cluster_id=cluster.id,
            pending_roles=["compute-vmware"]
        )
        self.assertTrue(objects.Cluster.has_compute_vmware_changes(cluster))
        objects.Node.delete(pending_compute_vmware_node)
        objects.Node.update(
            ready_compute_vmware_node, {'pending_deletion': True})
        self.assertTrue(objects.Cluster.has_compute_vmware_changes(cluster))

    def test_enable_settings_by_components(self):
        components = [{
            'name': 'network:neutron:tun',
            'bind': [['cluster:net_provider', 'neutron'],
                     ['cluster:net_segment_type', 'tun']]
        }, {
            'name': 'hypervisor:libvirt:kvm',
            'bind': [['settings:common.libvirt_type.value', 'kvm']]
        }, {
            'name': 'additional_service:sahara',
            'bind': ['settings:additional_components.sahara.value']
        }]
        default_editable_attributes = {
            'common': {'libvirt_type': {'value': 'qemu'}},
            'additional_components': {'sahara': {'value': False}}
        }

        release = self.env.create_release(
            version='2015.1-8.0',
            operating_system=consts.RELEASE_OS.ubuntu,
            modes=[consts.CLUSTER_MODES.ha_compact],
            components_metadata=components)

        self.env.create_plugin(
            name='plugin_with_test_network_for_neutron',
            package_version='4.0.0',
            fuel_version=['8.0'],
            components_metadata=self.env.get_default_components(
                name='network:neutron:test_network',
                bind=[['cluster:net_segment_type', 'tun']]))

        tests_data = [{
            'selected_components': ['network:neutron:tun',
                                    'hypervisor:libvirt:kvm',
                                    'additional_service:sahara'],
            'expected_values': {
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'segmentation_type': consts.NEUTRON_SEGMENT_TYPES.tun
            }
        }, {
            'selected_components': ['network:neutron:test_network',
                                    'hypervisor:libvirt:kvm',
                                    'additional_service:sahara'],
            'expected_values': {
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'segmentation_type': consts.NEUTRON_SEGMENT_TYPES.tun
            }
        }]
        for i, test_data in enumerate(tests_data):
            with mock.patch('objects.Cluster.get_default_editable_attributes',
                            return_value=default_editable_attributes):
                cluster = objects.Cluster.create({
                    'name': 'test-{0}'.format(i),
                    'release_id': release.id,
                    'components': test_data.get('selected_components', [])
                })
            editable_attrs = cluster.attributes.editable
            expected_values = test_data['expected_values']
            self.assertEqual(cluster.net_provider,
                             expected_values['net_provider'])
            if expected_values['segmentation_type']:
                self.assertEqual(cluster.network_config.segmentation_type,
                                 expected_values['segmentation_type'])
            self.assertEqual(
                editable_attrs[u'common'][u'libvirt_type'][u'value'], u'kvm')
            self.assertTrue(
                editable_attrs[u'additional_components'][u'sahara'][u'value'])

    def test_cleanup_openstack_config(self):
        cluster = self.env.create_cluster(
            api=False, nodes=[self.env.nodes[0].id])

        config = self.env.create_openstack_config(
            cluster_id=cluster.id, node_id=self.env.nodes[0].id,
            configuration={'key': 'value'})
        self.assertTrue(config.is_active)

        objects.Cluster.update(cluster, {'nodes': []})

        self.db().refresh(config)
        self.assertFalse(config.is_active)


class TestClusterObjectVirtRoles(BaseTestCase):

    def setUp(self):
        super(TestClusterObjectVirtRoles, self).setUp()
        self.env.create(
            nodes_kwargs=[
                {'roles': ['virt']},
                {'roles': ['virt']},
                {'roles': ['controller']},
            ]
        )

        self.env.nodes[0].vms_conf = [
            {'id': 1, 'cpu': 1, 'mem': 2},
            {'id': 2, 'cpu': 1, 'mem': 2},
        ]

        self.env.nodes[1].vms_conf = [
            {'id': 1, 'cpu': 1, 'mem': 2},
            {'id': 2, 'cpu': 1, 'mem': 2},
        ]

    def test_set_vms_created_state(self):
        objects.Cluster.set_vms_created_state(self.env.clusters[0])

        for node in self.env.nodes:
            for conf in node.vms_conf:
                self.assertTrue(conf['created'])

    def test_reset_vms_created_state(self):
        objects.Cluster.set_vms_created_state(self.env.clusters[0])

        objects.Node.reset_vms_created_state(self.env.nodes[0])

        for conf in self.env.nodes[0].vms_conf:
            self.assertFalse(conf['created'])

        for conf in self.env.nodes[1].vms_conf:
            self.assertTrue(conf['created'])


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
        objects.ClusterPlugins.set_attributes(self.cluster.id,
                                              plugin.id,
                                              enabled=True)
        self.db.refresh(plugin)
        return plugin

    def test_no_plugins_no_additional_roles(self):
        roles = objects.Cluster.get_roles(self.cluster)
        self.assertItemsEqual(roles.keys(), ['role_a', 'role_b'])

    def test_plugin_adds_new_roles(self):
        self.create_plugin({
            'role_c': {
                'name': 'Role C', 'description': 'Role C is ...', },
        })

        roles = objects.Cluster.get_roles(self.cluster)
        self.assertItemsEqual(roles.keys(), ['role_a', 'role_b', 'role_c'])

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
            'roles: role_a, role_x'
            .format(plugin_in_conflict.id))

        with self.assertRaisesRegexp(errors.AlreadyExists, message_pattern):
            objects.Cluster.get_roles(self.cluster)


class TestClusterObjectGetNetworkManager(BaseTestCase):
    def setUp(self):
        super(TestClusterObjectGetNetworkManager, self).setUp()
        self.env.create(cluster_kwargs={'net_provider': 'neutron'})

    def test_get_default(self):
        nm = objects.Cluster.get_network_manager()
        self.assertIs(nm, NetworkManager)

    def check_neutron_network_manager(
            self, net_provider, version, expected_manager):
        cluster = self.env.clusters[0]
        cluster.net_provider = net_provider
        cluster.release.version = version
        nm = objects.Cluster.get_network_manager(cluster)
        self.assertIs(expected_manager, nm)

    def test_raise_if_unknown(self):
        cluster = self.env.clusters[0]
        cluster.net_provider = "invalid_data"
        self.assertRaisesWithMessage(
            Exception,
            'The network provider "invalid_data" is not supported.',
            objects.Cluster.get_network_manager, cluster
        )

    def test_neutron_network_managers_by_version(self):
        for version, manager_class in (
            ('2014.2.2-6.0', NeutronManagerLegacy),
            ('2014.2.2-6.1', NeutronManager61),
            ('2015.6.7-7.0', NeutronManager70),
            ('2016.1.1-8.0', NeutronManager80),
        ):
            self.check_neutron_network_manager(
                consts.CLUSTER_NET_PROVIDERS.neutron,
                version, manager_class
            )

    def test_nova_network_managers_by_version(self):
        for version, manager_class in (
            ('2014.2.2-6.0', NovaNetworkManagerLegacy),
            ('2014.2.2-6.1', NovaNetworkManager61),
            ('2015.6.7-7.0', NovaNetworkManager70),
        ):
            self.check_neutron_network_manager(
                consts.CLUSTER_NET_PROVIDERS.nova_network,
                version, manager_class
            )

    def test_get_neutron_80(self):
        self.env.clusters[0].release.version = '2014.2.2-8.0'
        nm = objects.Cluster.get_network_manager(self.env.clusters[0])
        self.assertEqual(nm, NeutronManager80)


class TestNetworkGroup(BaseTestCase):

    def test_upgrade_range_mask_from_cidr(self):
        cluster = self.env.create_cluster(api=False)
        ng = cluster.network_groups[0]
        objects.NetworkGroup._update_range_from_cidr(
            ng, "192.168.10.0/24")
        ip_range = ng.ip_ranges[0]
        self.assertEqual("192.168.10.1", ip_range.first)
        self.assertEqual("192.168.10.254", ip_range.last)

    def test_upgrade_range_mask_from_cidr_use_gateway(self):
        cluster = self.env.create_cluster(api=False)
        ng = cluster.network_groups[0]
        objects.NetworkGroup._update_range_from_cidr(
            ng, "192.168.10.0/24",
            use_gateway=True)
        ip_range = ng.ip_ranges[0]
        self.assertEqual("192.168.10.2", ip_range.first)
        self.assertEqual("192.168.10.254", ip_range.last)

    def test_get_default_networkgroup(self):
        ng = objects.NetworkGroup.get_default_admin_network()
        self.assertIsNotNone(ng)

    def test_is_untagged(self):
        cluster = self.env.create_cluster(api=False)
        admin_net = objects.NetworkGroup.get_default_admin_network()
        mgmt_net = objects.NetworkGroup.get_from_node_group_by_name(
            objects.Cluster.get_default_group(cluster).id,
            consts.NETWORKS.management)
        self.assertTrue(objects.NetworkGroup.is_untagged(admin_net))
        self.assertFalse(objects.NetworkGroup.is_untagged(mgmt_net))


class TestRelease(BaseTestCase):

    def test_get_all_components(self):
        release = self.env.create_release(
            version='2015.1-8.0',
            operating_system=consts.RELEASE_OS.ubuntu,
            modes=[consts.CLUSTER_MODES.ha_compact],
            components_metadata=self.env.get_default_components(
                name='hypervisor:test_component_1'))

        self.env.create_plugin(
            name='plugin_with_components',
            package_version='4.0.0',
            fuel_version=['8.0'],
            releases=[{
                'repository_path': 'repositories/ubuntu',
                'version': '2015.1-8.0',
                'os': 'ubuntu',
                'mode': ['ha'],
                'deployment_scripts_path': 'deployment_scripts/'}],
            components_metadata=[dict(
                name='storage:test_component_2',
                label='Test storage',
                incompatible=[{
                    'name': 'hypervisor:test_component_1',
                    'message': 'component_2 not compatible with component_1'}]
            ), dict(
                name='network:test_component_3',
                label='Test network',
                compatible=[{
                    'name': 'storage:test_component_2'}])]
        )

        components = objects.Release.get_all_components(release)

        self.assertItemsEqual(components, [{
            'name': 'hypervisor:test_component_1',
            'compatible': [
                {'name': 'hypervisor:*'},
                {'name': 'storage:object:block:swift'}],
            'incompatible': [
                {'name': 'network:*'},
                {'name': 'additional_service:*'},
                {'name': 'storage:test_component_2',
                 'message': 'Not compatible with Test storage'}]}, {
            'name': 'storage:test_component_2',
            'label': 'Test storage',
            'compatible': [
                {'name': 'network:test_component_3'}],
            'incompatible': [
                {'name': 'hypervisor:test_component_1',
                 'message': 'component_2 not compatible with component_1'}]}, {
            'name': 'network:test_component_3',
            'label': 'Test network',
            'compatible': [
                {'name': 'storage:test_component_2'}],
            'incompatible': [
                {'name': 'hypervisor:test_component_1',
                 'message': 'Not compatible with hypervisor:test_component_1'}]
        }])

    def test_contain_component(self):
        components = [
            {'name': 'test_component_type_1:test_component_1'},
            {'name': 'test_component_type_2:*'}
        ]

        self.assertTrue(objects.Release._contain(
            components, 'test_component_type_1:test_component_1'))

        self.assertTrue(objects.Release._contain(
            components, 'test_component_type_2:test_component_3'))

        self.assertFalse(objects.Release._contain(
            components, 'test_component_type_1:test_component_4'))


class TestOpenstackConfig(BaseTestCase):

    def setUp(self):
        super(TestOpenstackConfig, self).setUp()

        self.env.create(
            nodes_kwargs=[
                {'role': 'controller', 'status': 'ready'},
                {'role': 'compute', 'status': 'ready'},
                {'role': 'cinder', 'status': 'ready'},
            ])

        self.cluster = self.env.clusters[0]
        self.nodes = self.env.nodes

    def test_create(self):
        config = objects.OpenstackConfig.create({
            'cluster_id': self.cluster.id,
            'configuration': {'key': 'value'},
        })
        self.assertEqual(config.cluster_id, self.cluster.id)
        self.assertEqual(config.config_type,
                         consts.OPENSTACK_CONFIG_TYPES.cluster)
        self.assertTrue(config.is_active)

        config = objects.OpenstackConfig.create({
            'cluster_id': self.cluster.id,
            'node_id': self.nodes[0].id,
            'configuration': {'key': 'value'},
        })
        self.assertEqual(config.cluster_id, self.cluster.id)
        self.assertEqual(config.node_id, self.nodes[0].id)
        self.assertEqual(config.config_type,
                         consts.OPENSTACK_CONFIG_TYPES.node)
        self.assertTrue(config.is_active)

        config = objects.OpenstackConfig.create({
            'cluster_id': self.cluster.id,
            'node_role': 'cinder',
            'configuration': {'key': 'value'},
        })
        self.assertEqual(config.cluster_id, self.cluster.id)
        self.assertEqual(config.node_role, 'cinder')
        self.assertEqual(config.config_type,
                         consts.OPENSTACK_CONFIG_TYPES.role)
        self.assertTrue(config.is_active)

    def test_create_override(self):
        config_1 = objects.OpenstackConfig.create({
            'cluster_id': self.cluster.id,
            'configuration': {'key': 'value'},
        })

        self.assertTrue(config_1.is_active)

        config_2 = objects.OpenstackConfig.create({
            'cluster_id': self.cluster.id,
            'configuration': {'key': 'value'},
        })

        self.assertTrue(config_2.is_active)
        self.assertFalse(config_1.is_active)

    def test_disable(self):
        config = objects.OpenstackConfig.create({
            'cluster_id': self.cluster.id,
            'configuration': {'key': 'value'},
        })

        objects.OpenstackConfig.disable(config)
        self.assertFalse(config.is_active)


class TestIPAddrObject(BaseTestCase):

    def test_get_intersecting_ip(self):
        admin_netg = self.db.query(objects.NetworkGroup.model).filter_by(
            name=consts.NETWORKS.fuelweb_admin
        ).first()

        ip_addr_one = objects.IPAddr.model(
            ip_addr='10.20.0.3',
            network=admin_netg.id
        )

        ip_addr_two = objects.IPAddr.model(
            ip_addr='10.20.0.4',
            network=admin_netg.id
        )
        self.db.add_all([ip_addr_one, ip_addr_two])
        self.db.flush()

        intersect = objects.IPAddr.get_intersecting_ip(ip_addr_two,
                                                       '10.20.0.3')
        self.assertEqual(intersect, ip_addr_one)

        intersect = objects.IPAddr.get_intersecting_ip(ip_addr_two,
                                                       '10.20.0.5')
        self.assertIsNone(intersect, ip_addr_one)

        intersect = objects.IPAddr.get_intersecting_ip(ip_addr_one,
                                                       '10.20.0.3')
        self.assertIsNone(intersect)
