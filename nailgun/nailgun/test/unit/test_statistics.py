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

from mock import patch

from nailgun.test.base import BaseTestCase

from nailgun import consts
from nailgun.objects import Cluster
from nailgun.objects import ReleaseCollection
from nailgun.settings import settings
from nailgun.statistics.installation_info import InstallationInfo
from nailgun.statistics.statsenderd import StatsSender


FEATURE_MIRANTIS = {'feature_groups': ['mirantis']}
FEATURE_EXPERIMENTAL = {'feature_groups': ['experimental']}


class TestStatistics(BaseTestCase):

    def test_release_info(self):
        info = InstallationInfo()
        f_info = info.fuel_release_info()
        self.assertDictEqual(f_info, settings.VERSION)

    def test_get_attributes_centos(self):
        self.env.upload_fixtures(['openstack'])
        info = InstallationInfo()
        release = ReleaseCollection.filter_by(None, operating_system='CentOS')
        cluster_data = self.env.create_cluster(
            release_id=release[0].id
        )
        cluster = Cluster.get_by_uid(cluster_data['id'])
        editable = cluster.attributes.editable
        attr_key_list = [a[1] for a in info.attributes_white_list]
        attrs_dict = info.get_attributes(editable)
        self.assertEqual(
            set(attr_key_list),
            set(attrs_dict.keys())
        )

    def test_get_attributes_ubuntu(self):
        self.env.upload_fixtures(['openstack'])
        info = InstallationInfo()
        release = ReleaseCollection.filter_by(None, operating_system='Ubuntu')
        cluster_data = self.env.create_cluster(
            release_id=release[0].id
        )
        cluster = Cluster.get_by_uid(cluster_data['id'])
        editable = cluster.attributes.editable
        attr_key_list = [a[1] for a in info.attributes_white_list]
        attrs_dict = info.get_attributes(editable)
        self.assertEqual(
            # no vlan splinters for ubuntu
            set(attr_key_list) - set(('vlan_splinters', 'vlan_splinters_ovs')),
            set(attrs_dict.keys())
        )

    def test_get_empty_attributes(self):
        info = InstallationInfo()
        trash_attrs = {'some': 'trash', 'nested': {'n': 't'}}
        result = info.get_attributes(trash_attrs)
        self.assertDictEqual({}, result)

    def test_get_attributes_exception_handled(self):
        info = InstallationInfo()
        variants = [
            None,
            [],
            {},
            {'common': None},
            {'common': []},
            {'common': {'libvirt_type': {}}},
            {'common': {'libvirt_type': 3}},
        ]
        for attrs in variants:
            result = info.get_attributes(attrs)
            self.assertDictEqual({}, result)

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
            cluster_kwargs={'mode': consts.CLUSTER_MODES.ha_full,
                            'libvirt_type': 'quemu'},
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
        self.assertEquals('qemu', cluster_info['attributes']['libvirt_type'])
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
            self.assertEquals(node_info['manufacturer'], node.manufacturer)

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

    def check_collector_urls(self, server):
        self.assertEqual(
            StatsSender().build_collector_url("COLLECTOR_ACTION_LOGS_URL"),
            settings.COLLECTOR_ACTION_LOGS_URL.format(collector_server=server)
        )
        self.assertEqual(
            StatsSender().build_collector_url("COLLECTOR_INST_INFO_URL"),
            settings.COLLECTOR_INST_INFO_URL.format(collector_server=server)
        )
        self.assertEqual(
            StatsSender().build_collector_url("COLLECTOR_PING_URL"),
            settings.COLLECTOR_PING_URL.format(collector_server=server)
        )

    @patch.dict('nailgun.settings.settings.VERSION', FEATURE_MIRANTIS)
    def test_mirantis_collector_urls(self):
        self.check_collector_urls(StatsSender.COLLECTOR_MIRANTIS_SERVER)

    @patch.dict('nailgun.settings.settings.VERSION', FEATURE_EXPERIMENTAL)
    def test_community_collector_urls(self):
        self.check_collector_urls(StatsSender.COLLECTOR_COMMUNITY_SERVER)
