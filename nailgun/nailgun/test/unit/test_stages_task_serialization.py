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
import yaml

from nailgun import consts
from nailgun import objects
from nailgun.orchestrator.base_serializers import NetworkDeploymentSerializer
from nailgun.orchestrator import deployment_graph
from nailgun.orchestrator import tasks_serializer
from nailgun.test import base


def update_nodes_net_info(cluster, nodes):
    return nodes


class BaseTaskSerializationTest(base.BaseTestCase):

    TASKS = """"""

    def setUp(self):
        super(BaseTaskSerializationTest, self).setUp()
        self.release = self.env.create_release(
            api=False)
        self.cluster = self.env.create_cluster(
            api=False, release_id=self.release.id)
        self.nodes = [
            self.env.create_node(
                roles=['controller'], cluster_id=self.cluster.id),
            self.env.create_node(
                roles=['controller'], primary_roles=['controller'],
                cluster_id=self.cluster.id),
            self.env.create_node(
                roles=['cinder', 'compute'], cluster_id=self.cluster.id)]
        self.all_uids = [n.uid for n in self.nodes]
        self.cluster.deployment_tasks = yaml.load(self.TASKS)


class BaseTaskSerializationTestUbuntu(base.BaseTestCase):
    TASKS = """"""

    def setUp(self):
        super(BaseTaskSerializationTestUbuntu, self).setUp()

        self._requests_mock = mock.patch(
            'nailgun.utils.debian.requests.get',
            return_value=mock.Mock(text='Archive: test'))
        self._requests_mock.start()

        self.release = self.env.create_release(
            api=False, attributes_metadata=self.env.read_fixtures(
                ['openstack'])[1]['fields']['attributes_metadata'])
        self.cluster = self.env.create_cluster(
            api=False, release_id=self.release.id)
        self.nodes = [
            self.env.create_node(
                roles=['controller'], cluster_id=self.cluster.id),
            self.env.create_node(
                roles=['primary-controller'], cluster_id=self.cluster.id),
            self.env.create_node(
                roles=['cinder', 'compute'], cluster_id=self.cluster.id)]
        self.all_uids = [n.uid for n in self.nodes]
        self.cluster.deployment_tasks = yaml.load(self.TASKS)

    def tearDown(self):
        self._requests_mock.stop()
        super(BaseTaskSerializationTestUbuntu, self).tearDown()


class TestHooksSerializersUbuntu(BaseTaskSerializationTestUbuntu):
    def test_create_repo_ubuntu(self):
        task_config = {'id': 'upload_mos_repos',
                       'type': 'upload_file',
                       'role': '*'}
        self.cluster.release.operating_system = consts.RELEASE_OS.ubuntu
        task = tasks_serializer.UploadMOSRepo(
            task_config, self.cluster, self.nodes)
        serialized = list(task.serialize())
        self.assertEqual(len(serialized), 17)
        self.assertEqual(serialized[0]['type'], 'shell')
        self.assertEqual(
            serialized[0]['parameters']['cmd'], '> /etc/apt/sources.list')
        self.assertEqual(serialized[1]['type'], 'upload_file')
        self.assertEqual(serialized[2]['type'], 'upload_file')
        self.assertEqual(serialized[3]['type'], 'upload_file')
        self.assertEqual(serialized[4]['type'], 'upload_file')
        self.assertEqual(serialized[5]['type'], 'upload_file')
        self.assertEqual(serialized[6]['type'], 'upload_file')
        self.assertEqual(serialized[7]['type'], 'upload_file')
        self.assertEqual(serialized[8]['type'], 'upload_file')
        self.assertEqual(serialized[9]['type'], 'upload_file')
        self.assertEqual(serialized[10]['type'], 'upload_file')
        self.assertEqual(serialized[11]['type'], 'upload_file')
        self.assertEqual(serialized[12]['type'], 'upload_file')
        self.assertEqual(serialized[13]['type'], 'upload_file')
        self.assertEqual(serialized[14]['type'], 'upload_file')
        self.assertEqual(serialized[15]['type'], 'upload_file')
        self.assertEqual(serialized[16]['type'], 'shell')
        self.assertEqual(serialized[16]['parameters']['cmd'], 'apt-get update')
        self.assertItemsEqual(serialized[3]['uids'], self.all_uids)


class TestHooksSerializers(BaseTaskSerializationTest):

    def test_sync_puppet(self):
        task_config = {'id': 'rsync_mos_puppet',
                       'type': 'sync',
                       'role': '*',
                       'parameters': {'src': '/etc/puppet/{OPENSTACK_VERSION}',
                                      'dst': '/etc/puppet'}}
        task = tasks_serializer.RsyncPuppet(
            task_config, self.cluster, self.nodes)
        serialized = next(task.serialize())
        self.assertEqual(serialized['type'], 'sync')
        self.assertIn(
            self.cluster.release.version,
            serialized['parameters']['src'])

    def test_create_repo_centos(self):
        """Verify that repository is created with correct metadata."""
        task_config = {'id': 'upload_mos_repos',
                       'type': 'upload_file',
                       'role': '*'}
        self.cluster.release.operating_system = consts.RELEASE_OS.centos
        task = tasks_serializer.UploadMOSRepo(
            task_config, self.cluster, self.nodes)
        serialized = list(task.serialize())
        self.assertEqual(len(serialized), 5)
        self.assertEqual(serialized[0]['type'], 'upload_file')
        self.assertEqual(serialized[1]['type'], 'upload_file')
        self.assertEqual(serialized[2]['type'], 'upload_file')
        self.assertEqual(serialized[3]['type'], 'upload_file')
        self.assertEqual(serialized[4]['type'], 'shell')
        self.assertEqual(serialized[4]['parameters']['cmd'], 'yum clean all')
        self.assertItemsEqual(serialized[4]['uids'], self.all_uids)

    def test_serialize_rados_with_ceph(self):
        task_config = {'id': 'restart_radosgw',
                       'type': 'shell',
                       'role': ['controller', 'primary-controller'],
                       'stage': 'post-deployment',
                       'parameters': {'cmd': '/cmd.sh', 'timeout': 60}}
        self.nodes.append(self.env.create_node(
            roles=['ceph-osd'], cluster_id=self.cluster.id))
        task = tasks_serializer.RestartRadosGW(
            task_config, self.cluster, self.nodes)
        serialized = list(task.serialize())
        self.assertEqual(len(serialized), 1)
        self.assertEqual(serialized[0]['type'], 'shell')
        self.assertEqual(
            serialized[0]['parameters']['cmd'],
            task_config['parameters']['cmd'])

    def test_serialzize_rados_wo_ceph(self):
        task_config = {'id': 'restart_radosgw',
                       'type': 'shell',
                       'role': ['controller', 'primary-controller'],
                       'stage': 'post-deployment',
                       'parameters': {'cmd': '/cmd.sh', 'timeout': 60}}
        task = tasks_serializer.RestartRadosGW(
            task_config, self.cluster, self.nodes)
        self.assertFalse(task.should_execute())

    @mock.patch.object(NetworkDeploymentSerializer, 'update_nodes_net_info')
    @mock.patch.object(objects.Node, 'all_roles')
    def test_upload_nodes_info(self, m_roles, m_update_nodes):
        # mark one node as ready so we can test for duplicates
        self.env.nodes[0].status = consts.NODE_STATUSES.ready
        self.db.flush()
        # add one node that will not be deployed
        discovered_node = self.env.create_node(
            roles=['compute'], cluster_id=self.cluster.id,
            status=consts.NODE_STATUSES.discover)

        m_roles.return_value = ['role_1', ]
        m_update_nodes.side_effect = lambda cluster, nodes: nodes

        self.cluster.release.version = '2014.1.1-6.1'
        dst = '/some/path/file.yaml'

        task_config = {
            'id': 'upload_nodes_info',
            'type': 'upload_file',
            'role': '*',
            'parameters': {
                'path': dst,
            },
        }

        task = tasks_serializer.UploadNodesInfo(
            task_config, self.cluster, self.nodes)
        serialized_tasks = list(task.serialize())
        self.assertEqual(len(serialized_tasks), 1)

        serialized_task = serialized_tasks[0]
        self.assertEqual(serialized_task['type'], 'upload_file')
        self.assertItemsEqual(serialized_task['uids'], self.all_uids)
        self.assertNotIn(discovered_node.uid, self.all_uids)
        self.assertEqual(serialized_task['parameters']['path'], dst)

        serialized_nodes = yaml.safe_load(
            serialized_task['parameters']['data'])
        serialized_uids = [n['uid'] for n in serialized_nodes['nodes']]
        self.assertItemsEqual(serialized_uids, self.all_uids)
        self.assertNotIn(discovered_node.uid, serialized_uids)

    def test_update_hosts(self):
        # mark one node as ready so we can test for duplicates
        self.env.nodes[0].status = consts.NODE_STATUSES.ready
        self.db.flush()
        # add one node that will not be deployed
        discovered_node = self.env.create_node(
            roles=['compute'], cluster_id=self.cluster.id,
            status=consts.NODE_STATUSES.discover)

        task_config = {
            'id': 'upload_nodes_info',
            'type': 'puppet',
            'role': '*',
            'parameters': {
                'puppet_manifest': '/puppet/modules/modular/hosts/hosts.pp',
                'puppet_modules': '/puppet/modules',
                'timeout': 3600,
                'cwd': '/',
            },
        }

        task = tasks_serializer.UpdateHosts(
            task_config, self.cluster, self.nodes)
        serialized_tasks = list(task.serialize())
        self.assertEqual(len(serialized_tasks), 1)

        serialized_task = serialized_tasks[0]
        self.assertEqual(serialized_task['type'], 'puppet')
        self.assertItemsEqual(serialized_task['uids'], self.all_uids)
        self.assertNotIn(discovered_node.uid, self.all_uids)
        self.assertNotIn(discovered_node.uid, serialized_task['uids'])

    def test_copy_keys(self):
        task_config = {
            'id': 'copy_keys',
            'type': 'copy_files',
            'role': '*',
            'parameters': {
                'files': [{
                    'src': '/var/www/nailgun/keys/{CLUSTER_ID}/nova.key',
                    'dst': '/var/lib/astute/nova.key'}],
                'permissions': '0600',
                'dir_permissions': '0700'}}
        task = tasks_serializer.CopyKeys(
            task_config, self.cluster, self.nodes)
        serialized = next(task.serialize())
        self.assertEqual(serialized['type'], 'copy_files')
        files = []
        files.append({
            'src': '/var/www/nailgun/keys/{CLUSTER_ID}/nova.key'.
            format(CLUSTER_ID=self.cluster.id),
            'dst': '/var/lib/astute/nova.key'})
        self.assertItemsEqual(
            files, serialized['parameters']['files'])

    def test_generate_keys(self):
        task_config = {
            'id': 'generate_keys',
            'type': 'shell',
            'role': 'master',
            'parameters': {
                'cmd': ("sh /etc/puppet/modules/osnailyfacter/modular/generate"
                        "_keys.sh -i {CLUSTER_ID} -o 'mongodb' -s 'neutron nov"
                        "a ceph mysql' -p /etc/fuel/keys/"),
                'timeout': 180}}
        task = tasks_serializer.GenerateKeys(
            task_config, self.cluster, self.nodes)
        serialized = next(task.serialize())
        self.assertEqual(serialized['type'], 'shell')
        self.assertEqual(
            serialized['parameters']['cmd'],
            "sh /etc/puppet/modules/osnailyfacter/modular/generate_keys.sh -i "
            "{CLUSTER_ID} -o 'mongodb' -s 'neutron nova ceph mysql' -p "
            "/etc/fuel/keys/".format(CLUSTER_ID=self.cluster.id))

    def test_copy_keys_ceph(self):
        task_config = {
            'id': 'copy_keys_ceph',
            'type': 'copy_files',
            'role': '*',
            'parameters': {
                'files': [{
                    'src': '/var/lib/fuel/keys/{CLUSTER_ID}/ceph/ceph.pub',
                    'dst': '/var/lib/astute/ceph/ceph.pub'}],
                'permissions': '0600',
                'dir_permissions': '0700'}}
        task = tasks_serializer.CopyCephKeys(
            task_config, self.cluster, self.nodes)
        serialized = next(task.serialize())
        self.assertEqual(serialized['type'], 'copy_files')
        files = []
        files.append({
            'src': '/var/lib/fuel/keys/{CLUSTER_ID}/ceph/ceph.pub'.
            format(CLUSTER_ID=self.cluster.id),
            'dst': '/var/lib/astute/ceph/ceph.pub'})
        self.assertItemsEqual(
            files, serialized['parameters']['files'])

    def test_generate_keys_ceph(self):
        task_config = {
            'id': 'generate_keys_ceph',
            'type': 'shell',
            'role': 'master',
            'parameters': {
                'cmd': ("sh /etc/puppet/modules/osnailyfacter/modular/astute/"
                        "generate_keys.sh -i {CLUSTER_ID} -s 'ceph' -p /var/"
                        "lib/fuel/keys/"),
                'timeout': 180}}
        task = tasks_serializer.GenerateCephKeys(
            task_config, self.cluster, self.nodes)
        serialized = next(task.serialize())
        self.assertEqual(serialized['type'], 'shell')
        self.assertEqual(
            serialized['parameters']['cmd'],
            "sh /etc/puppet/modules/osnailyfacter/modular/astute/"
            "generate_keys.sh -i {CLUSTER_ID} -s 'ceph' -p /var/"
            "lib/fuel/keys/".format(CLUSTER_ID=self.cluster.id))

    def test_generate_haproxy_keys(self):
        cmd_template = "sh /etc/puppet/modules/osnailyfacter/modular/" \
                       "astute/generate_haproxy_keys.sh -i {CLUSTER_ID} " \
                       "-h {CN_HOSTNAME} -o 'haproxy' -p /var/lib/fuel/keys/"
        task_config = {
            'id': 'generate_haproxy_keys',
            'type': 'shell',
            'role': 'master',
            'parameters': {
                'cmd': cmd_template,
                'timeout': 180}}
        task = tasks_serializer.GenerateHaproxyKeys(
            task_config, self.cluster, self.nodes)
        serialized = next(task.serialize())
        self.assertEqual(serialized['type'], 'shell')
        editable = self.cluster.attributes.editable
        hostname = editable['public_ssl']['hostname']['value']
        expected_cmd = cmd_template.format(
            CLUSTER_ID=self.cluster.id, CN_HOSTNAME=hostname)
        self.assertEqual(expected_cmd, serialized['parameters']['cmd'])


class TestPreTaskSerialization(BaseTaskSerializationTestUbuntu):

    TASKS = ("""
        - id: pre_deployment_start
          type: stage

        - id: pre_deployment
          type: stage
          requires: [pre_deployment_start]

        - id: deploy_start
          type: stage
          requires: [pre_deployment]

        - id: upload_core_repos
          type: upload_file
          role: '*'
          required_for: [pre_deployment]
          requires: [pre_deployment_start]

        - id: rsync_core_puppet
          type: sync
          role: '*'
          required_for: [pre_deployment]
          requires: [upload_core_repos]
          parameters:
            src: /etc/puppet/{OPENSTACK_VERSION}/
            dst: /etc/puppet
            timeout: 180

        - id: copy_keys
          type: copy_files
          role: '*'
          required_for: [pre_deployment]
          requires: [generate_keys]
          parameters:
            files:
              - src: '{CLUSTER_ID}/nova.key'
                dst: 'nova.key'
            permissions: 0600
            dir_permissions: 0700

        - id: generate_keys
          type: shell
          role: 'master'
          requires: [pre_deployment_start]
          parameters:
            cmd: shorted_command
            timeout: 180
        """)

    def test_tasks_serialized_correctly(self):
        self.graph = deployment_graph.AstuteGraph(self.cluster)
        self.cluster.release.operating_system = consts.RELEASE_OS.ubuntu
        tasks = self.graph.pre_tasks_serialize(self.nodes)
        self.assertEqual(len(tasks), 20)
        tasks_tests = [('shell', ['master']),
                       ('shell', sorted(self.all_uids)),
                       ('upload_file', sorted(self.all_uids)),
                       ('upload_file', sorted(self.all_uids)),
                       ('upload_file', sorted(self.all_uids)),
                       ('upload_file', sorted(self.all_uids)),
                       ('upload_file', sorted(self.all_uids)),
                       ('upload_file', sorted(self.all_uids)),
                       ('upload_file', sorted(self.all_uids)),
                       ('upload_file', sorted(self.all_uids)),
                       ('upload_file', sorted(self.all_uids)),
                       ('upload_file', sorted(self.all_uids)),
                       ('upload_file', sorted(self.all_uids)),
                       ('upload_file', sorted(self.all_uids)),
                       ('upload_file', sorted(self.all_uids)),
                       ('upload_file', sorted(self.all_uids)),
                       ('upload_file', sorted(self.all_uids)),
                       ('copy_files', sorted(self.all_uids)),
                       ('sync', sorted(self.all_uids)),
                       ('shell', sorted(self.all_uids))]
        tasks_output = []
        for task in tasks:
            tasks_output.append((task['type'], sorted(task['uids'])))
        self.assertItemsEqual(tasks_tests, tasks_output)


class TestPostTaskSerialization(BaseTaskSerializationTest):

    TASKS = """
    - id: deploy_end
      type: stage

    - id: post_deployment_start
      type: stage
      requires: [deploy_end]

    - id: post_deployment
      type: stage
      requires: [post_deployment_start]

    - id: restart_radosgw
      type: shell
      role: [controller, primary-controller]
      required_for: [post_deployment]
      requires: [post_deployment_start]
      parameters:
        cmd: /etc/puppet/restart_radosgw.sh
        timeout: 180
    """

    def setUp(self):
        super(TestPostTaskSerialization, self).setUp()
        self.control_uids = [n.uid for n in self.nodes
                             if 'controller' in n.roles]
        self.graph = deployment_graph.AstuteGraph(self.cluster)

    def test_post_task_serialize_all_tasks(self):
        self.nodes.append(self.env.create_node(
            roles=['ceph-osd'], cluster_id=self.cluster.id))
        tasks = self.graph.post_tasks_serialize(self.nodes)
        self.assertEqual(len(tasks), 1)
        self.assertItemsEqual(tasks[0]['uids'], self.control_uids)
        self.assertEqual(tasks[0]['type'], 'shell')


class TestConditionalTasksSerializers(BaseTaskSerializationTest):

    TASKS = """
    - id: pre_deployment_start
      type: stage

    - id: pre_deployment
      type: stage
      requires: [pre_deployment_start]

    - id: deploy_start
      type: stage
      requires: [pre_deployment]

    - id: generic_uid
      type: upload_file
      role: '*'
      requires: [pre_deployment_start]
      condition: cluster:status == 'operational'
      parameters:
        cmd: /tmp/bash_script.sh
        timeout: 180
    - id: generic_second_task
      type: sync
      role: '*'
      requires: [generic_uid]
      required_for: [pre_deployment]
      condition: settings:enabled
      parameters:
        cmd: /tmp/bash_script.sh
        timeout: 180
    """

    def setUp(self):
        super(TestConditionalTasksSerializers, self).setUp()
        self.graph = deployment_graph.AstuteGraph(self.cluster)

    def test_conditions_satisfied(self):
        self.cluster.status = 'operational'
        self.cluster.attributes.editable = {'enabled': True}
        self.db.flush()

        tasks = self.graph.pre_tasks_serialize(self.nodes)
        self.assertEqual(len(tasks), 2)

        self.assertEqual(tasks[0]['type'], 'upload_file')
        self.assertEqual(tasks[1]['type'], 'sync')

    def test_conditions_not_satisfied(self):
        self.cluster.status = 'new'
        self.cluster.attributes.editable = {'enabled': False}
        self.db.flush()

        tasks = self.graph.pre_tasks_serialize(self.nodes)
        self.assertEqual(len(tasks), 0)
