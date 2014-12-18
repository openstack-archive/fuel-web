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


from mock import Mock
from mock import patch

import requests
import urllib3

from nailgun.test.base import BaseTestCase

from nailgun import consts
from nailgun.objects import Cluster
from nailgun.objects import ReleaseCollection
from nailgun.settings import settings
from nailgun.statistics.installation_info import InstallationInfo
from nailgun.statistics.statsenderd import StatsSender

FEATURE_MIRANTIS = {'feature_groups': ['mirantis']}
FEATURE_EXPERIMENTAL = {'feature_groups': ['experimental']}


class TestInstallationInfo(BaseTestCase):

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
        self.env.upload_fixtures(['openstack'])
        info = InstallationInfo()
        release = ReleaseCollection.filter_by(None, operating_system='CentOS')
        nodes_params = [
            {'roles': ['compute']},
            {'roles': ['compute']},
            {'roles': ['controller']}
        ]
        self.env.create(
            cluster_kwargs={
                'release_id': release[0].id,
                'mode': consts.CLUSTER_MODES.ha_full,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.nova_network},
            nodes_kwargs=nodes_params
        )
        self.env.create_node({'status': consts.NODE_STATUSES.discover})
        clusters_info = info.get_clusters_info()
        cluster = self.env.clusters[0]
        self.assertEquals(1, len(clusters_info))
        cluster_info = clusters_info[0]

        self.assertEquals(len(nodes_params), len(cluster_info['nodes']))
        self.assertEquals(len(nodes_params), cluster_info['nodes_num'])

        self.assertEquals(consts.CLUSTER_MODES.ha_full,
                          cluster_info['mode'])
        self.assertEquals(consts.CLUSTER_NET_PROVIDERS.nova_network,
                          cluster_info['net_provider'])
        self.assertEquals(consts.CLUSTER_STATUSES.new,
                          cluster_info['status'])
        self.assertEquals(False,
                          cluster_info['is_customized'])

        self.assertEquals(cluster.id,
                          cluster_info['id'])
        self.assertEquals(cluster.fuel_version,
                          cluster_info['fuel_version'])

        self.assertTrue('attributes' in cluster_info)

        self.assertTrue('release' in cluster_info)
        self.assertEquals(cluster.release.operating_system,
                          cluster_info['release']['os'])
        self.assertEquals(cluster.release.name,
                          cluster_info['release']['name'])
        self.assertEquals(cluster.release.version,
                          cluster_info['release']['version'])

        self.assertEquals(1, len(cluster_info['node_groups']))
        group_info = cluster_info['node_groups'][0]
        group = [ng for ng in cluster.node_groups][0]
        self.assertEquals(group.id,
                          group_info['id'])
        self.assertEquals(len(nodes_params),
                          len(group_info['nodes']))
        self.assertEquals(set([n.id for n in group.nodes]),
                          set(group_info['nodes']))

    def test_nodes_info(self):
        info = InstallationInfo()
        self.env.create(
            release_kwargs={
                'operating_system': consts.RELEASE_OS.centos
            },
            nodes_kwargs=[
                {'status': consts.NODE_STATUSES.ready,
                 'roles': ['controller', 'compute']},
                {'roles': [],
                 'pending_roles': ['compute']}
            ]
        )
        self.env.make_bond_via_api(
            'bond0', consts.OVS_BOND_MODES.active_backup,
            ['eth0', 'eth1'], node_id=self.env.nodes[0].id)
        nodes_info = info.get_nodes_info(self.env.nodes)
        self.assertEquals(len(self.env.nodes), len(nodes_info))
        for idx, node in enumerate(self.env.nodes):
            node_info = nodes_info[idx]
            self.assertEquals(node_info['id'], node.id)
            self.assertEquals(node_info['group_id'], node.group_id)
            self.assertListEqual(node_info['roles'], node.roles)
            self.assertEquals(node_info['os'], node.os_platform)

            self.assertEquals(node_info['status'], node.status)
            self.assertEquals(node_info['error_type'], node.error_type)
            self.assertEquals(node_info['online'], node.online)

            self.assertEquals(node_info['manufacturer'], node.manufacturer)
            self.assertEquals(node_info['platform_name'], node.platform_name)

            self.assertEquals(node_info['pending_addition'],
                              node.pending_addition)
            self.assertEquals(node_info['pending_deletion'],
                              node.pending_deletion)
            self.assertEquals(node_info['pending_roles'], node.pending_roles)

            self.assertEqual(
                node_info['nic_interfaces'],
                [{'id': i.id} for i in node.nic_interfaces]
            )
            self.assertEqual(
                node_info['bond_interfaces'],
                [{'id': i.id, 'slaves': [s.id for s in i.slaves]}
                 for i in node.bond_interfaces]
            )

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
        self.assertTrue('contact_info_provided' in info['user_information'])
        self.assertDictEqual(settings.VERSION, info['fuel_release'])


class TestStatisticsSender(BaseTestCase):

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

    @patch('nailgun.statistics.statsenderd.requests.get')
    def test_ping_ok(self, requests_get):
        requests_get.return_value = Mock(status_code=200)
        sender = StatsSender()

        self.assertTrue(sender.ping_collector())
        requests_get.assert_called_once_with(
            sender.build_collector_url("COLLECTOR_PING_URL"),
            timeout=settings.COLLECTOR_RESP_TIMEOUT)

    @patch('nailgun.statistics.statsenderd.requests.get')
    @patch('nailgun.statistics.statsenderd.logger.error')
    def test_ping_failed_on_connection_errors(self, log_error, requests_get):
        except_types = (
            urllib3.exceptions.DecodeError,
            urllib3.exceptions.ProxyError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.TooManyRedirects,
            requests.exceptions.HTTPError)

        for except_ in except_types:
            requests_get.side_effect = except_()
            self.assertFalse(StatsSender().ping_collector())
            log_error.assert_called_with("Collector ping failed: %s",
                                         type(except_()).__name__)

    @patch('nailgun.statistics.statsenderd.requests.get')
    @patch('nailgun.statistics.statsenderd.logger.exception')
    def test_ping_failed_on_exception(self, log_exception, requests_get):
        requests_get.side_effect = Exception("custom")

        self.assertFalse(StatsSender().ping_collector())
        log_exception.assert_called_once_with(
            "Collector ping failed: %s", "custom")

    @patch('nailgun.statistics.statsenderd.requests.post')
    def test_send_ok(self, requests_post):
        requests_post.return_value = Mock(status_code=200)
        sender = StatsSender()

        self.assertEqual(
            sender.send_data_to_url(
                url=sender.build_collector_url("COLLECTOR_ACTION_LOGS_URL"),
                data={}),
            requests_post.return_value
        )
        requests_post.assert_called_once_with(
            sender.build_collector_url("COLLECTOR_ACTION_LOGS_URL"),
            headers={'content-type': 'application/json'},
            data='{}',
            timeout=settings.COLLECTOR_RESP_TIMEOUT)

    @patch('nailgun.statistics.statsenderd.requests.post')
    @patch('nailgun.statistics.statsenderd.logger.error')
    def test_send_failed_on_connection_error(self, log_error, requests_post):
        except_types = (
            urllib3.exceptions.DecodeError,
            urllib3.exceptions.ProxyError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.TooManyRedirects)

        for except_ in except_types:
            requests_post.side_effect = except_()
            sender = StatsSender()
            self.assertIsNone(
                sender.send_data_to_url(
                    url=sender.build_collector_url(
                        "COLLECTOR_ACTION_LOGS_URL"),
                    data={})
            )
            log_error.assert_called_with(
                "Sending data to collector failed: %s",
                type(except_()).__name__)

    @patch('nailgun.statistics.statsenderd.requests.post')
    @patch('nailgun.statistics.statsenderd.logger.exception')
    def test_send_failed_on_exception(self, log_error, requests_post):
        requests_post.side_effect = Exception("custom")
        sender = StatsSender()
        self.assertIsNone(
            sender.send_data_to_url(
                url=sender.build_collector_url("COLLECTOR_ACTION_LOGS_URL"),
                data={})
        )
        log_error.assert_called_once_with(
            "Sending data to collector failed: %s", "custom")

    @patch('nailgun.statistics.statsenderd.time.sleep')
    def test_send_stats_once_after_dberror(self, sleep):
        def fn():
            # try to commit wrong data
            Cluster.create(
                {
                    "id": "500",
                    "release_id": "500"
                }
            )
            self.db.commit()

        ss = StatsSender()

        ss.send_stats_once()
        # one call was made (all went ok)
        self.assertEqual(sleep.call_count, 1)

        with patch.object(ss,
                          'must_send_stats',
                          fn):
            ss.send_stats_once()
        # no more calls was made because of exception
        self.assertEqual(sleep.call_count, 1)

        ss.send_stats_once()
        # one more call was made (all went ok)
        self.assertEqual(sleep.call_count, 2)
