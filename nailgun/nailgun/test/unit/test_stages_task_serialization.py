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
from nailgun.orchestrator import deployment_graph
from nailgun.orchestrator import tasks_serializer
from nailgun.test import base


PRE_STAGE = """
- id: upload_mos_repos
  type: upload_file
  role: '*'
  stage: pre_deployment

- id: rsync_mos_puppet
  type: sync
  role: '*'
  stage: pre_deployment
  requires: [upload_mos_repos]
  parameters:
    src: /etc/puppet/{OPENSTACK_VERSION}/
    dst: /etc/puppet
    timeout: 180
"""


class TestPreHooksSerializers(base.BaseTestCase):

    def setUp(self):
        super(TestPreHooksSerializers, self).setUp()
        self.nodes = [
            mock.Mock(uid='3', all_roles=['controller']),
            mock.Mock(uid='4', all_roles=['primary-controller']),
            mock.Mock(uid='5', all_roles=['cinder', 'compute'])]
        self.cluster = mock.Mock()
        self.cluster.release.orchestrator_data.repo_metadata = {
            '6.0': '{MASTER_IP}//{OPENSTACK_VERSION}'
        }

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


class TestPreTaskSerialization(base.BaseTestCase):

    def setUp(self):
        super(TestPreTaskSerialization, self).setUp()
        self.nodes = [
            mock.Mock(uid='3', all_roles=['controller']),
            mock.Mock(uid='4', all_roles=['primary-controller']),
            mock.Mock(uid='5', all_roles=['cinder', 'compute'])]
        self.cluster = mock.Mock()
        self.cluster.release.orchestrator_data.repo_metadata = {
            '6.0': '{MASTER_IP}//{OPENSTACK_VERSION}'
        }
        self.cluster.deployment_tasks = yaml.load(PRE_STAGE)
        self.all_uids = set([n.uid for n in self.nodes])
        self.graph = deployment_graph.AstuteGraph(self.cluster)

    def test_tasks_serialized_correctly(self):
        self.cluster.release.operating_system = consts.RELEASE_OS.ubuntu
        tasks = self.graph.pre_tasks_serialize(self.nodes)
        self.assertEqual(len(tasks), 3)
        self.assertEqual(tasks[0]['type'], 'upload_file')
        self.assertEqual(set(tasks[0]['uids']), self.all_uids)
        self.assertEqual(tasks[1]['type'], 'shell')
        self.assertEqual(set(tasks[1]['uids']), self.all_uids)
        self.assertEqual(tasks[2]['type'], 'sync')
        self.assertEqual(set(tasks[2]['uids']), self.all_uids)
