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

import yaml

from nailgun import consts
from nailgun.orchestrator import deployment_graph
from nailgun.orchestrator import tasks_serializer
from nailgun.test import base


class BaseTaskSerializationTest(base.BaseTestCase):

    TASKS = """"""

    def setUp(self):
        super(BaseTaskSerializationTest, self).setUp()
        self.release = self.env.create_release(
            api=False,
            orchestrator_data={'repo_metadata': {
                '6.0': '{MASTER_IP}//{OPENSTACK_VERSION}'}})
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
        self.assertEqual(len(serialized), 2)
        self.assertEqual(serialized[0]['type'], 'upload_file')
        self.assertEqual(serialized[1]['type'], 'shell')
        self.assertEqual(serialized[1]['parameters']['cmd'], 'yum clean all')
        self.assertItemsEqual(serialized[1]['uids'], self.all_uids)

    def test_create_repo_ubuntu(self):
        task_config = {'id': 'upload_mos_repos',
                       'type': 'upload_file',
                       'role': '*'}
        self.cluster.release.operating_system = consts.RELEASE_OS.ubuntu
        task = tasks_serializer.UploadMOSRepo(
            task_config, self.cluster, self.nodes)
        serialized = list(task.serialize())
        self.assertEqual(len(serialized), 2)
        self.assertEqual(serialized[0]['type'], 'upload_file')
        self.assertEqual(serialized[1]['type'], 'shell')
        self.assertEqual(serialized[1]['parameters']['cmd'], 'apt-get update')
        self.assertItemsEqual(serialized[1]['uids'], self.all_uids)

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

    def test_copy_keys(self):
        task_config = {
            'id': 'copy_keys',
            'type': 'copy_files',
            'role': '*',
            'parameters': {
                'srcs_and_dests': [
                    '/var/www/nailgun/keys/{CLUSTER_ID}/{KEY_NAME}.key',
                    '/var/lib/astute/{KEY_NAME}.key]'],
                'permissions': '0600',
                'dir_permissions': '0700'}}
        self.cluster.release.operating_system = consts.RELEASE_OS.ubuntu
        task = tasks_serializer.CopyKeys(
            task_config, self.cluster, self.nodes)
        serialized = next(task.serialize())
        self.assertEqual(serialized['type'], 'copy_files')
        files = []
        for key_name in consts.KEYS_TYPES:
            files.append((
                '/var/www/nailgun/keys/{CLUSTER_ID}/{KEY_NAME}.key'.format(
                    CLUSTER_ID=self.cluster.id, KEY_NAME=key_name),
                '/var/lib/astute/{KEY_NAME}.key]'.format(KEY_NAME=key_name)))
        self.assertItemsEqual(
            files, serialized['parameters']['srcs_and_dests'])

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
        self.cluster.release.operating_system = consts.RELEASE_OS.ubuntu
        task = tasks_serializer.GenerateKeys(
            task_config, self.cluster, self.nodes)
        serialized = next(task.serialize())
        self.assertEqual(serialized['type'], 'shell')
        self.assertEqual(
            serialized['parameters']['cmd'],
            "sh /etc/puppet/modules/osnailyfacter/modular/generate_keys.sh -i "
            "{CLUSTER_ID} -o 'mongodb' -s 'neutron nova ceph mysql' -p "
            "/etc/fuel/keys/".format(CLUSTER_ID=self.cluster.id))


class TestPreTaskSerialization(BaseTaskSerializationTest):

    TASKS = ("""
        - id: upload_core_repos
          type: upload_file
          role: '*'
          stage: pre_deployment

        - id: rsync_core_puppet
          type: sync
          role: '*'
          stage: pre_deployment
          requires: [upload_core_repos]
          parameters:
            src: /etc/puppet/{OPENSTACK_VERSION}/
            dst: /etc/puppet
            timeout: 180

        - id: copy_keys
          type: copy_files
          role: '*'
          stage: pre_deployment
          requires: [generate_keys]
          parameters:
            srcs_and_dests: ['{CLUSTER_ID}/{KEY_NAME}.key', '{KEY_NAME}.key']
            permissions: 0600
            dir_permissions: 0700

        - id: generate_keys
          type: shell
          role: 'master'
          stage: pre_deployment
          required_for: [rsync_keys]
          parameters:
            cmd: shorted_command
            timeout: 180
        """)

    def test_tasks_serialized_correctly(self):
        self.graph = deployment_graph.AstuteGraph(self.cluster)
        self.cluster.release.operating_system = consts.RELEASE_OS.ubuntu
        tasks = self.graph.pre_tasks_serialize(self.nodes)
        self.assertEqual(len(tasks), 5)
        tasks_tests = [('shell', set(['master'])),
                       ('upload_file', self.all_uids),
                       ('copy_files', self.all_uids),
                       ('sync', self.all_uids),
                       ('shell', self.all_uids)]
        tasks_output = []
        for task in tasks:
            tasks_output.append((task['type'], set(task['uids'])))
        self.assertItemsEqual(tasks_tests, tasks_output)


class TestPostTaskSerialization(BaseTaskSerializationTest):

    TASKS = """
    - id: restart_radosgw
      type: shell
      role: [controller, primary-controller]
      stage: post_deployment
      parameters:
        cmd: /etc/pupppet/restart_radosgw.sh
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
        self.assertEqual(tasks[0]['uids'], self.control_uids)
        self.assertEqual(tasks[0]['type'], 'shell')


class TestConditionalTasksSerializers(BaseTaskSerializationTest):

    TASKS = """
    - id: generic_uid
      type: upload_file
      role: '*'
      stage: pre_deployment
      condition: cluster:status == 'operational'
      parameters:
        cmd: /tmp/bash_script.sh
        timeout: 180
    - id: generic_second_task
      type: sync
      role: '*'
      stage: pre_deployment
      requires: [generic_uid]
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
