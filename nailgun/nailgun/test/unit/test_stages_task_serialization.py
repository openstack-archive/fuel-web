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

    def test_sync_time(self):
        task_config = {
            'id': 'sync_time',
            'type': 'shell',
            'role': '*',
            'parameters': {
                'cmd': ("ntpdate -u $(egrep '^server' /etc/ntp.conf | sed "
                        "'/^#/d' | awk '{print $2}')"),
                'timeout': 180,
                'retry': True
                }}
        task = tasks_serializer.SyncTime(
            task_config, self.cluster, self.nodes)
        serialized = next(task.serialize())
        self.assertEqual(serialized['type'], 'shell')
        self.assertEqual(
            serialized['parameters']['cmd'],
            "ntpdate -u $(egrep '^server' /etc/ntp.conf | sed "
            "'/^#/d' | awk '{print $2}')")
        self.assertEqual(serialized['parameters']['retry'], True)


class TestPreTaskSerialization(BaseTaskSerializationTest):

    TASKS = """
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

    - id: sync_time
      type: shell
      role: '*'
      stage: pre_deployment
      parameters:
        cmd: shorted_command
        retry: true
        timeout: 180
    """

    def test_tasks_serialized_correctly(self):
        self.graph = deployment_graph.AstuteGraph(self.cluster)
        self.cluster.release.operating_system = consts.RELEASE_OS.ubuntu
        tasks = self.graph.pre_tasks_serialize(self.nodes)
        self.assertEqual(len(tasks), 4)
        tasks_tests = [('upload_file', self.all_uids),
                       ('sync', self.all_uids),
                       ('shell', self.all_uids),
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
        self.assertItemsEqual(tasks[0]['uids'], self.control_uids)
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
