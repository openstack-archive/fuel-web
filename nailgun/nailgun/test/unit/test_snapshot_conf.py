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

from nailgun.test import base

from nailgun.settings import settings
from nailgun.task import task


class TestSnapshotConf(base.TestCase):

    def test_must_have_roles(self):
        conf = task.DumpTask.conf()
        self.assertIn('local', conf['dump'])
        self.assertIn('master', conf['dump'])
        self.assertIn('slave', conf['dump'])

    def test_local_host(self):
        conf = task.DumpTask.conf()
        # local role is abstract, but we have to make sure that it's
        # real localhost and there's only one host
        self.assertFalse(len(conf['dump']['local']['hosts']))

    @mock.patch('nailgun.task.task.socket')
    def test_master_injection(self, mock_socket):
        hostname = 'test-hostname-test'
        mock_socket.gethostname.return_value = hostname
        conf = task.DumpTask.conf()
        self.assertEqual(conf['dump']['master']['hosts'][0], {
            'hostname': hostname,
            'address': settings.MASTER_IP,
            'ssh-key': settings.SHOTGUN_SSH_KEY,
        })

    def test_postgres_injection(self):
        conf = task.DumpTask.conf()

        for object_ in conf['dump']['local']['objects']:
            if object_['type'] == 'postgres':
                self.assertEqual(
                    object_['dbhost'], settings.DATABASE['host'])
                self.assertEqual(
                    object_['dbname'], settings.DATABASE['name'])
                self.assertEqual(
                    object_['username'], settings.DATABASE['user'])
                self.assertEqual(
                    object_['password'], settings.DATABASE['passwd'])
                break
        else:
            self.fail("A `postgres` object MUST BE in `local` objects!")

    @mock.patch('nailgun.task.task.db')
    @mock.patch('nailgun.task.task.objects.Cluster')
    def test_slave_generating(self, mock_cluster, mock_db):

        (
            mock_db.return_value.query.return_value.filter.return_value.
            all.return_value
        ) = [
            mock.Mock(hostname='node1', ip="10.109.0.2", roles=[]),
            mock.Mock(hostname='node2', ip="10.109.0.5", roles=[]),
        ]

        mock_cluster.get_editable_attributes.return_value = {
            'service_user': {
                'name': {
                    'value': 'fuel',
                    'type': 'hidden'
                }
            }
        }
        conf = task.DumpTask.conf()

        self.assertIn({
            'hostname': 'node1',
            'address': '10.109.0.2',
            'ssh-user': 'fuel',
            'ssh-key': settings.SHOTGUN_SSH_KEY,
        }, conf['dump']['slave']['hosts'])

        self.assertIn({
            'hostname': 'node2',
            'address': '10.109.0.5',
            'ssh-user': 'fuel',
            'ssh-key': settings.SHOTGUN_SSH_KEY,
        }, conf['dump']['slave']['hosts'])

    @mock.patch('nailgun.task.task.db')
    @mock.patch('nailgun.task.task.objects.Cluster')
    def test_controller_generating(self, mock_cluster, mock_db):

        (
            mock_db.return_value.query.return_value.filter.return_value.
            all.return_value
        ) = [
            mock.Mock(hostname='node1', ip='10.109.0.1', roles=['controller',
                      'cinder']),
            mock.Mock(hostname='node2', roles=['compute']),
        ]

        mock_cluster.get_editable_attributes.return_value = {
            'service_user': {
                'name': {
                    'value': 'fuel',
                    'type': 'hidden'
                }
            }
        }
        conf = task.DumpTask.conf()

        self.assertIn({
            'hostname': 'node1',
            'address': '10.109.0.1',
            'ssh-user': 'fuel',
            'ssh-key': settings.SHOTGUN_SSH_KEY,
        }, conf['dump']['controller']['hosts'])

        self.assertNotIn({
            'hostname': 'node2',
            'ssh-user': 'fuel',
            'ssh-key': settings.SHOTGUN_SSH_KEY,
        }, conf['dump']['controller']['hosts'])

    @mock.patch('nailgun.task.task.db')
    @mock.patch('nailgun.task.task.objects.Cluster')
    def test_falling_back_to_root_ssh(self, mock_cluster, mock_db):

        (
            mock_db.return_value.query.return_value.filter.return_value.
            all.return_value
        ) = [
            mock.Mock(hostname='node1', ip="10.109.0.2", roles=[]),
            mock.Mock(hostname='node2', ip="10.109.0.5", roles=[]),
        ]

        mock_cluster.get_editable_attributes.return_value = {
            'editable': {}
        }
        conf = task.DumpTask.conf()

        self.assertIn({
            'hostname': 'node1',
            'address': '10.109.0.2',
            'ssh-user': 'root',
            'ssh-key': settings.SHOTGUN_SSH_KEY,
        }, conf['dump']['slave']['hosts'])

        self.assertIn({
            'hostname': 'node2',
            'address': '10.109.0.5',
            'ssh-user': 'root',
            'ssh-key': settings.SHOTGUN_SSH_KEY,
        }, conf['dump']['slave']['hosts'])
