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

from nailgun.test.base import BaseTestCase

from nailgun import consts
from nailgun.settings import settings
from nailgun.statistics.installation_info import InstallationInfo


class TestStatistics(BaseTestCase):

    def test_release_info(self):
        info = InstallationInfo()
        f_info = info.fuel_release_info()
        self.assertDictEqual(f_info, settings.VERSION)

    def test_clusters_info(self):
        info = InstallationInfo()
        nodes_params = [
            {'roles': ['compute']},
            {'roles': ['compute']},
            {'roles': ['controller']}
        ]
        self.env.create(
            release_kwargs={
                'operating_system': consts.RELEASE_OS.centos
            },
            cluster_kwargs={'mode': consts.CLUSTER_MODES.ha_full},
            nodes_kwargs=nodes_params
        )
        self.env.create_node({'status': consts.NODE_STATUSES.discover})
        clusters_info = info.get_clusters_info()
        self.assertEquals(1, len(clusters_info))
        cluster_info = clusters_info[0]
        self.assertEquals(len(nodes_params), len(cluster_info['nodes']))
        self.assertEquals(len(nodes_params), cluster_info['nodes_num'])
        self.assertEquals(consts.CLUSTER_MODES.ha_full, cluster_info['mode'])
        self.assertTrue('release' in cluster_info)
        self.assertTrue('attributes' in cluster_info)
        self.assertEquals(consts.RELEASE_OS.centos,
                          cluster_info['release']['os'])

    def test_nodes_info(self):
        info = InstallationInfo()
        self.env.create(
            release_kwargs={
                'operating_system': consts.RELEASE_OS.centos
            },
            nodes_kwargs=[
                {'status': consts.NODE_STATUSES.ready,
                 'roles': ['controller', 'compute']},
                {'roles': []}
            ]
        )
        nodes_info = info.get_nodes_info(self.env.nodes)
        self.assertEquals(len(self.env.nodes), len(nodes_info))
        for idx, node in enumerate(self.env.nodes):
            node_info = nodes_info[idx]
            self.assertEquals(node_info['id'], node.id)
            self.assertEquals(node_info['status'], node.status)
            self.assertListEqual(node_info['roles'], node.roles)
            self.assertEquals(node_info['os'], node.os_platform)

    def test_installation_info(self):
        info = InstallationInfo()
        nodes_params = [
            {'roles': ['compute']},
            {'roles': ['compute']},
            {'roles': ['controller']}
        ]
        self.env.create(
            release_kwargs={
                'operating_system': consts.RELEASE_OS.centos
            },
            cluster_kwargs={},
            nodes_kwargs=nodes_params
        )
        unallocated_nodes_params = [
            {'status': consts.NODE_STATUSES.discover},
            {'status': consts.NODE_STATUSES.discover}
        ]
        for unallocated_node in unallocated_nodes_params:
            self.env.create_node(**unallocated_node)
        info = info.get_installation_info()
        self.assertEquals(1, info['clusters_num'])
        self.assertEquals(len(nodes_params), info['allocated_nodes_num'])
        self.assertEquals(len(unallocated_nodes_params),
                          info['unallocated_nodes_num'])
        self.assertTrue('master_node_uid' in info)
        self.assertDictEqual(settings.VERSION, info['fuel_release'])

    def test_sanitation(self):
        info = InstallationInfo()
        self.assertDictEqual({}, info.sanitise_data({}))
        self.assertDictEqual({}, info.sanitise_data({'password': 'xx'}))
        self.assertDictEqual(
            {'f': 'n'},
            info.sanitise_data({'password': 'xx', 'f': 'n'})
        )
        self.assertListEqual([], info.sanitise_data([]))
        self.assertListEqual(
            [1, 2, 'password'],
            info.sanitise_data([1, 2, 'password'])
        )
        self.assertListEqual(
            sorted([{'f': 'n'}, {'a': 'b'}]),
            info.sanitise_data([{'password': 'x', 'f': 'n'}, {'a': 'b'}])
        )
