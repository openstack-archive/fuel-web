# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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
import os
import shutil
import tempfile

from nailgun.db.sqlalchemy.models import Cluster
from nailgun import objects
from nailgun.test.base import BaseTestCase
from nailgun.utils import logs as logs_utils


class TestNodeLogsUtils(BaseTestCase):

    def create_env(self, nodes):
        cluster = self.env.create(nodes_kwargs=nodes)

        cluster_db = self.db.query(Cluster).get(cluster['id'])
        objects.NodeCollection.prepare_for_deployment(cluster_db.nodes)
        self.db.flush()
        return cluster_db

    def test_generate_log_paths_for_node(self):
        cluster = self.create_env([{'roles': ['controller']}])
        node = cluster.nodes[0]
        prefix = "/var/log/remote"

        log_paths = logs_utils.generate_log_paths_for_node(node, prefix)
        self.assertItemsEqual(
            ['links', 'old', 'bak', 'new'],
            log_paths.keys())

        self.assertEqual(len(log_paths['links']), 1)
        self.assertEqual(
            "{prefix}/{node_ip}".format(prefix=prefix, node_ip=node.ip),
            log_paths['links'][0])
        self.assertEqual(
            "{prefix}/{node_ip}".format(prefix=prefix, node_ip=node.ip),
            log_paths['old'])
        fqdn = objects.Node.get_node_fqdn(node)
        self.assertEqual(
            "{prefix}/{node_fqdn}".format(
                prefix=prefix,
                node_fqdn=fqdn),
            log_paths['new'])
        self.assertEqual(
            "{prefix}/{node_fqdn}.bak".format(
                prefix=prefix,
                node_fqdn=fqdn),
            log_paths['bak'])

    def test_delete_node_logs(self):
        prefix = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, prefix)

        cluster = self.create_env([{'roles': ['controller']}])
        node = cluster.nodes[0]

        log_paths = logs_utils.generate_log_paths_for_node(node, prefix)

        link = log_paths['links'][0]
        os.symlink(log_paths['old'], link)

        folder = log_paths['new']
        os.mkdir(folder)

        file_ = log_paths['bak']
        with open(file_, 'w') as f:
            f.write("RANDOMCONTENT")

        logs_utils.delete_node_logs(node, prefix)

        self.assertTrue(
            all(not os.path.exists(path) for path in [link, folder, file_]))

    @mock.patch('os.path.islink', side_effect=OSError)
    def test_delete_node_no_existing_logs(self, _):
        """Only checks whether errors are passing silently.
        That's why there's no assertions, just expecting no errors.
        """
        prefix = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, prefix)

        cluster = self.create_env([{'roles': ['controller']}])
        node = cluster.nodes[0]
        logs_utils.delete_node_logs(node, prefix)
