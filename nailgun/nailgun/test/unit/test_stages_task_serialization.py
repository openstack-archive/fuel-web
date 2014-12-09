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

from nailgun import consts
from nailgun.orchestrator import tasks_serializer
from nailgun.test import base


class TestPreHooksSerializers(base.BaseTestCase):

    def setUp(self):
        super(TestPreHooksSerializers, self).setUp()
        self.nodes = [
            mock.Mock(uid='3', all_roles=['controller']),
            mock.Mock(uid='4', all_roles=['primary-controller']),
            mock.Mock(uid='5', all_roles=['cinder', 'compute'])]
        self.cluster = mock.Mock()

    def test_sync_puppet(self):
        task = tasks_serializer.SyncPuppet(self.cluster, self.nodes)
        self.assertTrue(task.condition())
        serialized = task.serialize()
        self.assertEqual(serialized['type'], 'sync')

    def test_create_repo_centos(self):
        """Verify that repository is created with correct metadata."""
        self.cluster.release.operating_system = consts.RELEASE_OS.centos
        task = tasks_serializer.UpdateRepo(self.cluster, self.nodes)
        self.assertTrue(task.condition())
        serialized = task.serialize()
        self.assertEqual(serialized['type'], 'upload_file')

    def test_create_repo_ubuntu(self):
        self.cluster.release.operating_system = consts.RELEASE_OS.ubuntu
        task = tasks_serializer.UpdateRepo(self.cluster, self.nodes)
        self.assertTrue(task.condition())
        serialized = task.serialize()
        self.assertEqual(serialized['type'], 'upload_file')

    def test_regenerate_metadata_centos(self):
        self.cluster.release.operating_system = consts.RELEASE_OS.centos
        task = tasks_serializer.RegenerateRepoMetadata(
            self.cluster, self.nodes)
        self.assertTrue(task.condition())
        serialized = task.serialize()
        self.assertEqual(serialized['type'], 'shell')

    def test_regenerate_metadata_ubuntu(self):
        self.cluster.release.operating_system = consts.RELEASE_OS.ubuntu
        task = tasks_serializer.RegenerateRepoMetadata(
            self.cluster, self.nodes)
        self.assertTrue(task.condition())
        serialized = task.serialize()
        self.assertEqual(serialized['type'], 'shell')

    def test_update_time(self):
        task = tasks_serializer.UpdateTime(self.cluster, self.nodes)
        self.assertTrue(task.condition())
        serialized = task.serialize()
        self.assertEqual(serialized['type'], 'shell')


@mock.patch('nailgun.orchestrator.tasks_serializer.objects.Node.all_roles')
class TestControllerdependentSerializers(base.BaseTestCase):

    def find_correct_node(self, node):
        for n in self.nodes:
            if n.uid == node.uid:
                return n.all_roles

    def setUp(self):
        super(TestControllerdependentSerializers, self).setUp()
        self.nodes = [
            mock.Mock(uid='3', all_roles=['controller']),
            mock.Mock(uid='4', all_roles=['primary-controller']),
            mock.Mock(uid='5', all_roles=['cinder', 'compute'])]
        self.cluster = mock.Mock()

    def test_update_no_quorum_serialized(self, all_roles):
        self.cluster.status = consts.CLUSTER_STATUSES.new
        all_roles.side_effect = self.find_correct_node
        task = tasks_serializer.UpdateNoQuorum(self.cluster, self.nodes)
        serialized = task.serialize()
        self.assertEqual(serialized['uids'], ['4'])

    def test_upload_glance_image(self, all_roles):
        self.cluster.status = consts.CLUSTER_STATUSES.new
        all_roles.side_effect = self.find_correct_node
        task = tasks_serializer.UploadGlance(self.cluster, self.nodes)
        serialized = task.serialize()
        self.assertEqual(serialized['uids'], ['4'])
