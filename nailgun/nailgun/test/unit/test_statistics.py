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
from mock import PropertyMock

import datetime
import os
import requests
import six
import urllib3

from nailgun.test.base import BaseTestCase

from nailgun import consts
from nailgun.db.sqlalchemy.models import plugins
from nailgun.objects import Cluster
from nailgun.objects import OpenStackWorkloadStats
from nailgun.objects import OpenStackWorkloadStatsCollection
from nailgun.objects import ReleaseCollection
from nailgun.settings import settings
from nailgun.statistics import errors
from nailgun.statistics.installation_info import InstallationInfo
from nailgun.statistics.oswl_collector import collect as oswl_collect_once
from nailgun.statistics.oswl_saver import oswl_data_checksum
from nailgun.statistics.oswl_saver import oswl_statistics_save
from nailgun.statistics.statsenderd import StatsSender
from nailgun.statistics import utils

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

    def test_network_configuration(self):
        info = InstallationInfo()
        # Checking nova network configuration
        nova = consts.CLUSTER_NET_PROVIDERS.nova_network
        self.env.create(cluster_kwargs={
            'mode': consts.CLUSTER_MODES.ha_full,
            'net_provider': nova
        })
        clusters_info = info.get_clusters_info()
        cluster_info = clusters_info[0]
        self.assertTrue('network_configuration' in cluster_info)
        network_config = cluster_info['network_configuration']

        for field in ('fixed_network_size', 'fixed_networks_vlan_start',
                      'fixed_networks_amount', 'net_manager'):
            self.assertIn(field, network_config)

        # Checking neutron network configuration
        neutron = consts.CLUSTER_NET_PROVIDERS.neutron
        self.env.create(cluster_kwargs={
            'mode': consts.CLUSTER_MODES.ha_full,
            'net_provider': neutron
        })
        clusters_info = info.get_clusters_info()
        # Clusters info is unordered list, so we should find required
        # cluster_info
        cluster_info = filter(lambda x: x['net_provider'] == neutron,
                              clusters_info)[0]
        self.assertTrue('network_configuration' in cluster_info)
        network_config = cluster_info['network_configuration']

        for field in ('segmentation_type', 'net_l23_provider'):
            self.assertIn(field, network_config)

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
            'bond0', consts.BOND_MODES.active_backup,
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

    def test_plugins_info(self):
        info = InstallationInfo()

        cluster = self.env.create_cluster(api=False)

        plugin_kwargs = self.env.get_default_plugin_metadata()
        plugin_obj = plugins.Plugin(**plugin_kwargs)

        self.db.add(plugin_obj)
        self.db.flush()

        plugin_kwargs["id"] = plugin_obj.id

        cluster_plugin_kwargs = {
            "cluster_id": cluster.id,
            "plugin_id": plugin_obj.id
        }
        cluster_plugin = plugins.ClusterPlugins(**cluster_plugin_kwargs)

        self.db.add(cluster_plugin)
        self.db.flush()

        expected_attributes_names = (
            "id",
            "name",
            "version",
            "releases",
            "fuel_version",
            "package_version",
        )

        expected_info = dict(
            [(key, value) for key, value in six.iteritems(plugin_kwargs)
             if key in expected_attributes_names]
        )

        expected = [expected_info]
        actual = info.get_cluster_plugins_info(cluster)
        self.assertEqual(expected, actual)

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
            StatsSender().build_collector_url("COLLECTOR_OSWL_INFO_URL"),
            settings.COLLECTOR_OSWL_INFO_URL.format(collector_server=server)
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

    def test_skipped_action_logs(self):

        class Response(object):
            status_code = 200

            def json(self):
                return {
                    'status': 'ok',
                    'action_logs': [{'external_id': 1, 'status': 'skipped'}]}

        sender = StatsSender()
        commit = 'nailgun.db.sqlalchemy.DeadlockDetectingSession.commit'
        with patch.object(sender, 'send_data_to_url',
                          return_value=Response()):
            with patch.object(sender, 'is_status_acceptable',
                              return_value=True):
                with patch(commit) as mocked_commit:
                    sender.send_log_serialized([{'external_id': 1}], [1])
                    self.assertEqual(0, mocked_commit.call_count)

    @patch('nailgun.statistics.statsenderd.time.sleep')
    @patch('nailgun.statistics.statsenderd.dithered')
    @patch('nailgun.db.sqlalchemy.fixman.settings.'
           'STATS_ENABLE_CHECK_INTERVAL', 0)
    @patch('nailgun.db.sqlalchemy.fixman.settings.'
           'COLLECTOR_PING_INTERVAL', 1)
    def test_send_stats_once_after_dberror(self, dithered, sleep):
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
        # one call with STATS_ENABLE_CHECK_INTERVAL was made (all went ok)
        self.assertEqual(sleep.call_count, 1)
        dithered.assert_called_with(0)

        with patch.object(ss,
                          'must_send_stats',
                          fn):
            ss.send_stats_once()
        # one more call with COLLECTOR_PING_INTERVAL value
        self.assertEqual(sleep.call_count, 2)
        dithered.assert_called_with(1)

        ss.send_stats_once()
        # one more call was made (all went ok)
        self.assertEqual(sleep.call_count, 3)

    @patch('nailgun.statistics.statsenderd.StatsSender.send_data_to_url')
    def test_oswl_nothing_to_send(self, send_data_to_url):
        dt = datetime.datetime.utcnow()
        obj_data = {
            'cluster_id': 1,
            'resource_type': consts.OSWL_RESOURCE_TYPES.vm,
            'created_date': dt.date(),
            'updated_time': dt.time(),
            'resource_checksum': ""
        }
        obj = OpenStackWorkloadStats.create(obj_data)
        self.assertEqual(
            OpenStackWorkloadStats.get_last_by(
                1, consts.OSWL_RESOURCE_TYPES.vm),
            obj
        )

        StatsSender().send_oswl_info()
        # Nothing to send as it doesn't send today's records. Today's are not
        # sent as they are not complete and can be updated during the day.
        self.assertEqual(send_data_to_url.call_count, 0)

    @patch('nailgun.db.sqlalchemy.fixman.settings.OSWL_COLLECT_PERIOD', 0)
    @patch('nailgun.statistics.statsenderd.StatsSender.send_data_to_url')
    def test_oswl_send_todays_record(self, send_data_to_url):
        dt = datetime.datetime.utcnow()
        obj_data = {
            'cluster_id': 1,
            'resource_type': consts.OSWL_RESOURCE_TYPES.vm,
            'created_date': dt.date(),
            'updated_time': dt.time(),
            'resource_checksum': ""
        }
        obj = OpenStackWorkloadStats.create(obj_data)
        self.assertEqual(
            OpenStackWorkloadStats.get_last_by(
                1, consts.OSWL_RESOURCE_TYPES.vm),
            obj
        )

        StatsSender().send_oswl_info()
        self.assertEqual(send_data_to_url.call_count, 1)

    def check_oswl_data_send_result(self, send_data_to_url, status, is_sent):
        # make yesterdays record (today's will not be sent)
        dt = datetime.datetime.utcnow() - datetime.timedelta(days=1)
        obj_data = {
            'cluster_id': 1,
            'resource_type': consts.OSWL_RESOURCE_TYPES.vm,
            'created_date': dt.date(),
            'updated_time': dt.time(),
            'resource_checksum': ""
        }
        obj = OpenStackWorkloadStats.create(obj_data)
        self.assertEqual(
            OpenStackWorkloadStats.get_last_by(
                1, consts.OSWL_RESOURCE_TYPES.vm),
            obj
        )
        rec_id = obj.id
        self.assertEqual(obj.is_sent, False)

        # emulate the answer from requests.post()
        class response(object):

            status_code = 200

            data = {
                "status": "ok",
                "text": "ok",
                "oswl_stats": [{
                    "master_node_uid": "",
                    "id": rec_id,
                    "status": status
                }]
            }

            def __getitem__(self, key):
                return self.data[key]

            @classmethod
            def json(cls):
                return cls.data

        send_data_to_url.return_value = response

        sender = StatsSender()
        sender.send_oswl_info()

        obj_data_sent = {'oswl_stats': [{
            'id': rec_id,
            'cluster_id': 1,
            'created_date': dt.date().isoformat(),
            'updated_time': dt.time().isoformat(),
            'resource_type': 'vm',
            'resource_checksum': '',
            'master_node_uid': None,
            'resource_data': None,
        }]}
        send_data_to_url.assert_called_once_with(
            url=sender.build_collector_url("COLLECTOR_OSWL_INFO_URL"),
            data=obj_data_sent)

        obj = OpenStackWorkloadStats.get_last_by(
            1, consts.OSWL_RESOURCE_TYPES.vm)
        self.assertEqual(obj.is_sent, is_sent)
        OpenStackWorkloadStats.delete(obj)
        send_data_to_url.reset_mock()

    @patch('nailgun.statistics.statsenderd.StatsSender.send_data_to_url')
    def test_oswl_data_send_results(self, send_data_to_url):
        status_vs_sent = {
            "added": True,
            "updated": True,
            "failed": False
        }
        for status, is_sent in status_vs_sent.iteritems():
            self.check_oswl_data_send_result(send_data_to_url, status, is_sent)


class TestOSWLCollectingUtils(BaseTestCase):

    components_to_mock = {
        "nova": {
            "servers": [
                {
                    "id": 1,
                    "status": "running",
                    "OS-EXT-STS:power_state": 1,
                    "created": "date_of_creation",
                    "hostId": "test_host_id",
                    "tenant_id": "test_tenant_id",
                    "image": {"id": "test_image_id"},
                    "flavor": {"id": "test_flavor_id"},
                },
            ],
            "flavors": [
                {
                    "id": 2,
                    "ram": 64,
                    "vcpus": 4,
                    "OS-FLV-EXT-DATA:ephemeral": 1,
                    "disk": 1,
                    "swap": 16,
                },
            ],
            "images": [
                {
                    "id": 4,
                    "minDisk": 1,
                    "minRam": 64,
                    "OS-EXT-IMG-SIZE:size": 13000000,
                    "created": "some_date_of_creation",
                    "updated": "some_date_of_update"
                },
            ],
            "client": {"version": "v1.1"}
        },
        "cinder": {
            "volumes": [
                {
                    "id": 3,
                    "availability_zone": "test_availability_zone",
                    "encrypted": False,
                    "bootable": False,
                    "status": "available",
                    "volume_type": "test_volume",
                    "size": 1,
                    "os-vol-host-attr:host": "test-node",
                    "snapshot_id": None,
                    "attachments": "test_attachments",
                    "os-vol-tenant-attr:tenant_id": "test_tenant",
                },
            ],
            "client": {"version": "v1"}
        },
        "keystone": {
            "tenants": [
                {
                    "id": 5,
                    "enabled": True,
                },
            ],
            "users": [
                {
                    "id": "test_user_id",
                    "enabled": True,
                    "tenantId": "test_tenant_id",
                }
            ],
            "version": "v2.0"
        },
    }

    def _prepare_client_provider_mock(self):
        client_provider_mock = Mock()

        clients_version_attr_path = {
            "nova": ["client", "version"],
            "cinder": ["client", "version"],
            "keystone": ["version"]
        }
        setattr(client_provider_mock, "clients_version_attr_path",
                clients_version_attr_path)

        return client_provider_mock

    def _update_mock_with_complex_dict(self, root_mock, attrs_dict):
        for key, value in six.iteritems(attrs_dict):
            attr_name = key
            attr_value = value

            if isinstance(value, dict):
                attr_value = Mock()
                self._update_mock_with_complex_dict(
                    attr_value, value
                )
            elif isinstance(value, list):
                attr_value = Mock()

                to_return = []
                for data in value:
                    attr_value_element = Mock()
                    attr_value_element.to_dict.return_value = data

                    to_return.append(attr_value_element)

                attr_value.list.return_value = to_return

            setattr(root_mock, attr_name, attr_value)

    def test_get_nested_attr(self):
        expected_attr = Mock()
        intermediate_attr = Mock(spec=["expected_attr"])
        containing_obj = Mock(spec=["intermediate_attr"])

        intermediate_attr.expected_attr = expected_attr
        containing_obj.intermediate_attr = intermediate_attr

        existing_attr_path = ["intermediate_attr", "expected_attr"]
        self.assertEqual(
            expected_attr,
            utils._get_nested_attr(containing_obj, existing_attr_path)
        )

        missing_attrs_pathes = [
            ["missing_attr", "expected_attr"],
            ["intermediate_attr", "missing_attr"],
        ]
        for attr_path in missing_attrs_pathes:
            self.assertIsNone(
                utils._get_nested_attr(containing_obj, attr_path)
            )

    def test_get_oswl_info(self):
        expected = {
            "vm": [
                {
                    "id": 1,
                    "status": "running",
                    "power_state": 1,
                    "created_at": "date_of_creation",
                    "image_id": "test_image_id",
                    "flavor_id": "test_flavor_id",
                    "host_id": "test_host_id",
                    "tenant_id": "test_tenant_id",
                },
            ],
            "flavor": [
                {
                    "id": 2,
                    "ram": 64,
                    "vcpus": 4,
                    "ephemeral": 1,
                    "disk": 1,
                    "swap": 16,
                },
            ],
            "image": [
                {
                    "id": 4,
                    "minDisk": 1,
                    "minRam": 64,
                    "sizeBytes": 13000000,
                    "created_at": "some_date_of_creation",
                    "updated_at": "some_date_of_update"
                },
            ],
            "volume": [
                {
                    "id": 3,
                    "availability_zone": "test_availability_zone",
                    "encrypted_flag": False,
                    "bootable_flag": False,
                    "status": "available",
                    "volume_type": "test_volume",
                    "size": 1,
                    "host": "test-node",
                    "snapshot_id": None,
                    "attachments": "test_attachments",
                    "tenant_id": "test_tenant",
                },
            ],
            "tenant": [
                {
                    "id": 5,
                    "enabled_flag": True,
                },
            ],
            "keystone_user": [
                {
                    "id": "test_user_id",
                    "enabled_flag": True,
                    "tenant_id": "test_tenant_id",
                },
            ],
        }

        client_provider_mock = self._prepare_client_provider_mock()

        self._update_mock_with_complex_dict(client_provider_mock,
                                            self.components_to_mock)

        for resource_name, expected_data in six.iteritems(expected):
            actual = utils.get_info_from_os_resource_manager(
                client_provider_mock, resource_name
            )
            self.assertEqual(actual, expected_data)

    def test_different_api_versions_handling_for_tenants(self):
        keystone_v2_component = {
            "keystone": {
                "tenants": [
                    {
                        "id": 5,
                        "enabled": True,
                    },
                ],
                "version": "v2.0"
            },
        }

        keystone_v3_component = {
            "keystone": {
                "projects": [
                    {
                        "id": 5,
                        "enabled": True,
                    },
                ],
                "version": "v3.0"
            },
        }

        client_provider_mock = self._prepare_client_provider_mock()
        self._update_mock_with_complex_dict(client_provider_mock,
                                            keystone_v2_component)
        client_provider_mock.keystone.tenants.list.assert_called_once()

        client_provider_mock = self._prepare_client_provider_mock()
        self._update_mock_with_complex_dict(client_provider_mock,
                                            keystone_v3_component)
        client_provider_mock.keystone.projects.list.assert_called_once()

    def test_different_api_versions_handling_for_users(self):
        keystone_v2_component = {
            "keystone": {
                "users": [
                    {
                        "id": "test_user_id",
                        "enabled": True,
                        "tenantId": "test_tenant_id",
                    }
                ],
                "version": "v2.0"
            },
        }

        keystone_v3_component = {
            "keystone": {
                "users": [
                    {
                        "id": "test_user_id",
                        "enabled": True,
                        "default_project_id": "test_tenant_id",
                    }
                ],
                "version": "v3"
            },
        }

        client_provider_mock = self._prepare_client_provider_mock()
        self._update_mock_with_complex_dict(client_provider_mock,
                                            keystone_v2_component)
        kc_v2_info = utils.get_info_from_os_resource_manager(
            client_provider_mock, consts.OSWL_RESOURCE_TYPES.keystone_user
        )

        client_provider_mock = self._prepare_client_provider_mock()
        self._update_mock_with_complex_dict(client_provider_mock,
                                            keystone_v3_component)
        kc_v3_info = utils.get_info_from_os_resource_manager(
            client_provider_mock, consts.OSWL_RESOURCE_TYPES.keystone_user
        )

        self.assertEqual(kc_v2_info, kc_v3_info)

    def test_additional_display_opts_supplied(self):
        expected_display_options = {"search_opts": {"all_tenants": 1}}

        client_provider_mock = self._prepare_client_provider_mock()
        self._update_mock_with_complex_dict(client_provider_mock,
                                            self.components_to_mock)

        utils.get_info_from_os_resource_manager(
            client_provider_mock, consts.OSWL_RESOURCE_TYPES.vm
        )
        client_provider_mock.nova.servers.list.assert_called_once_with(
            **expected_display_options
        )

        utils.get_info_from_os_resource_manager(
            client_provider_mock, consts.OSWL_RESOURCE_TYPES.volume
        )
        client_provider_mock.cinder.volumes.list.assert_called_once_with(
            **expected_display_options
        )

    def test_set_proxy_func(self):
        def check_proxy():
            with utils.set_proxy(new_proxy):
                self.assertEqual(os.environ.get("http_proxy"), new_proxy)

        def raise_inside_context():
            with utils.set_proxy(new_proxy):
                raise Exception("Just an error")

        expected = {"http_proxy": "test"}
        new_proxy = "fake_proxy"

        # check that proxy old value is restored
        # after exit from context manager w/ and w/o exception
        with patch.dict("os.environ", expected):
            check_proxy()
            self.assertEqual(os.environ.get("http_proxy"),
                             expected["http_proxy"])

            raise_inside_context()
            self.assertEqual(os.environ.get("http_proxy"),
                             expected["http_proxy"])

        # check that env variable is deleted
        # after exit from context manager w/ and w/o exception
        check_proxy()
        self.assertNotIn("http_proxy", os.environ)

        raise_inside_context()
        self.assertNotIn("http_proxy", os.environ)

    def test_get_value_from_nested_dict_func(self):
        dict_to_retrieve = {
            "containing_dict": {
                "intermediate_dict": {
                    "expected_attr": "test",
                },
            },
        }

        expected = "test"

        key_path = ["containing_dict", "intermediate_dict", "expected_attr"]

        retrieved = utils._get_value_from_nested_dict(
            dict_to_retrieve, key_path
        )
        self.assertEqual(retrieved, expected)

        retrieved = utils._get_value_from_nested_dict(
            dict_to_retrieve, []
        )
        self.assertIsNone(retrieved)

        retrieved = utils._get_value_from_nested_dict(
            [], key_path
        )
        self.assertIsNone(retrieved)

    def test_get_online_controller(self):
        node_name = "test"
        self.env.create(
            nodes_kwargs=[{"online": True,
                           "roles": ["controller"],
                           "name": node_name}]
        )

        cluster = self.env.clusters[0]
        online_controller = utils._get_online_controller(cluster)
        self.assertIsNotNone(online_controller)
        self.assertEqual(online_controller.name, node_name)

        cluster.nodes[0].online = False
        self.assertRaises(errors.NoOnlineControllers,
                          utils._get_online_controller,
                          cluster)


class TestOpenStackClientProvider(BaseTestCase):

    @patch("nailgun.statistics.utils.ClientProvider.credentials",
           new_callable=PropertyMock)
    def test_clients_providing(self, creds_mock):
        fake_credentials = (
            "fake_username",
            "fake_password",
            "fake_tenant_name",
            "fake_auth_url"
        )
        auth_kwargs = {
            "username": fake_credentials[0],
            "password": fake_credentials[1],
            "tenant_name": fake_credentials[2],
            "project_name": fake_credentials[2],
            "auth_url": fake_credentials[3]
        }

        creds_mock.return_value = fake_credentials
        client_provider = utils.ClientProvider(cluster=None)

        nova_client_path = ("nailgun.statistics.utils."
                            "nova_client.Client")
        cinder_client_path = ("nailgun.statistics.utils."
                              "cinder_client.Client")

        return_value_mock = Mock()

        with patch(nova_client_path,
                   Mock(return_value=return_value_mock)) as nova_client_mock:

            self.assertTrue(client_provider.nova is return_value_mock)

            client_provider.nova

            nova_client_mock.assert_called_once_with(
                settings.OPENSTACK_API_VERSION["nova"],
                *fake_credentials,
                service_type=consts.NOVA_SERVICE_TYPE.compute
            )

        with patch(cinder_client_path,
                   Mock(return_value=return_value_mock)) as cinder_client_mock:

            self.assertTrue(client_provider.cinder is return_value_mock)

            client_provider.cinder

            cinder_client_mock.assert_called_once_with(
                settings.OPENSTACK_API_VERSION["cinder"],
                *fake_credentials
            )

        with patch.object(client_provider, "_get_keystone_client",
                          return_value=return_value_mock) as get_kc_mock:
            kc = client_provider.keystone
            self.assertTrue(kc is return_value_mock)

            client_provider.keystone

            get_kc_mock.assert_called_with_once(**auth_kwargs)

    def test_fail_if_no_online_controllers(self):
        self.env.create(
            nodes_kwargs=[{"online": False, "roles": ["controller"]}]
        )
        cluster = self.env.clusters[0]
        client_provider = utils.ClientProvider(cluster)

        with self.assertRaises(errors.NoOnlineControllers):
            client_provider.credentials

    @patch("nailgun.statistics.utils.keystone_client_v3.Client")
    @patch("nailgun.statistics.utils.keystone_client_v2.Client")
    @patch("nailgun.statistics.utils.keystone_discover.Discover")
    def test_get_keystone_client(self, kd_mock, kc_v2_mock, kc_v3_mock):
        version_data_v2 = [{"version": (2, 0)}]
        version_data_v3 = [{"version": (3, 0)}]
        mixed_version_data = [{"version": (4, 0)}, {"version": (3, 0)}]
        not_supported_version_data = [{"version": (4, 0)}]

        auth_creds = {"auth_url": "fake"}

        client_provider = utils.ClientProvider(cluster=None)

        discover_inst_mock = Mock()
        kd_mock.return_value = discover_inst_mock

        kc_v2_inst_mock = Mock()
        kc_v2_mock.return_value = kc_v2_inst_mock

        kc_v3_inst_mock = Mock()
        kc_v3_mock.return_value = kc_v3_inst_mock

        def check_returned(version_data, client_class_mock, client_inst_mock):
            discover_inst_mock.version_data = Mock(return_value=version_data)

            kc_client_inst = client_provider._get_keystone_client(auth_creds)

            kd_mock.assert_called_with(**auth_creds)

            self.assertTrue(kc_client_inst is client_inst_mock)

            client_class_mock.assert_called_with(**auth_creds)

        check_returned(version_data_v2, kc_v2_mock, kc_v2_inst_mock)
        check_returned(version_data_v3, kc_v3_mock, kc_v3_inst_mock)
        check_returned(mixed_version_data, kc_v3_mock, kc_v3_inst_mock)

        fail_message = ("Failed to discover keystone version "
                        "for auth_url {0}"
                        .format(auth_creds["auth_url"]))

        discover_inst_mock.version_data = \
            Mock(return_value=not_supported_version_data)

        self.assertRaisesRegexp(
            Exception,
            fail_message,
            client_provider._get_keystone_client,
            auth_creds
        )

    def test_get_auth_credentials(self):
        expected_username = "test"
        expected_password = "test"
        expected_tenant = "test"
        expected_auth_host = "0.0.0.0"
        expected_auth_url = "http://{0}:{1}/{2}/".format(
            expected_auth_host, settings.AUTH_PORT,
            settings.OPENSTACK_API_VERSION["keystone"])

        expected = (expected_username, expected_password, expected_tenant,
                    expected_auth_url)

        cluster = self.env.create_cluster(api=False)
        updated_attributes = {
            "editable": {
                "workloads_collector": {
                    "username": {"value": expected_username},
                    "password": {"value": expected_password},
                    "tenant": {"value": expected_tenant}
                }
            }
        }
        Cluster.update_attributes(cluster, updated_attributes)

        get_host_for_auth_path = ("nailgun.statistics.utils."
                                  "_get_host_for_auth")

        with patch(get_host_for_auth_path,
                   return_value=expected_auth_host):
            client_provider = utils.ClientProvider(cluster)
            creds = client_provider.credentials

            self.assertEqual(expected, creds)


class TestOSWLCollector(BaseTestCase):

    vms_info = [{
        "id": 1,
        "status": "running",
    }]

    def collect_for_operational_cluster(self, get_info_mock):
        cluster = self.env.create_cluster(
            api=False,
            status=consts.CLUSTER_STATUSES.operational
        )
        cls_id = cluster.id
        get_info_mock.return_value = self.vms_info
        oswl_collect_once(consts.OSWL_RESOURCE_TYPES.vm)
        last = OpenStackWorkloadStats.get_last_by(
            cls_id, consts.OSWL_RESOURCE_TYPES.vm)
        upd_time = last.updated_time
        res_data = {
            'added': [{'time': upd_time.isoformat(), 'id': 1}],
            'removed': [],
            'modified': [],
            'current': self.vms_info}
        self.assertEqual(last.resource_data, res_data)
        return cls_id, res_data

    def update_cluster_status_and_oswl_data(self, cls_id, status):
        cls = Cluster.get_by_uid(cls_id)
        Cluster.update(cls, {'status': status})
        oswl_collect_once(consts.OSWL_RESOURCE_TYPES.vm)
        return OpenStackWorkloadStats.get_last_by(
            cls_id, consts.OSWL_RESOURCE_TYPES.vm)

    @patch('nailgun.statistics.oswl_collector.utils.ClientProvider')
    @patch('nailgun.statistics.oswl_collector.utils.set_proxy')
    @patch('nailgun.statistics.oswl_collector.utils.'
           'get_info_from_os_resource_manager')
    def test_skip_collection_for_errorful_cluster(self, get_info_mock, *_):
        error_cluster = self.env.create(
            api=False,
            nodes_kwargs=[{"roles": ["controller"], "online": False}],
            cluster_kwargs={"name": "error",
                            "status": consts.CLUSTER_STATUSES.operational}
        )
        normal_cluster = self.env.create(
            api=False,
            nodes_kwargs=[{"roles": ["controller"], "online": True}],
            cluster_kwargs={"name": "normal",
                            "status": consts.CLUSTER_STATUSES.operational}
        )

        get_info_mock.return_value = self.vms_info

        oswl_collect_once(consts.OSWL_RESOURCE_TYPES.vm)

        last_for_error_clsr = OpenStackWorkloadStats.get_last_by(
            error_cluster["id"], consts.OSWL_RESOURCE_TYPES.vm)
        self.assertIsNone(last_for_error_clsr)

        last_for_normal_clsr = OpenStackWorkloadStats.get_last_by(
            normal_cluster["id"], consts.OSWL_RESOURCE_TYPES.vm)
        self.assertIsNotNone(last_for_normal_clsr)

        upd_time = last_for_normal_clsr.updated_time
        res_data = {
            'added': [{'time': upd_time.isoformat(), 'id': 1}],
            'removed': [],
            'modified': [],
            'current': self.vms_info}
        self.assertEqual(last_for_normal_clsr.resource_data, res_data)

    @patch('nailgun.statistics.oswl_collector.utils.ClientProvider')
    @patch('nailgun.statistics.oswl_collector.utils.get_proxy_for_cluster')
    @patch('nailgun.statistics.oswl_collector.utils.set_proxy')
    @patch('nailgun.statistics.oswl_collector.utils.'
           'get_info_from_os_resource_manager')
    def test_clear_data_for_changed_cluster(self, get_info_mock, *_):
        cls_id, res_data = self.collect_for_operational_cluster(get_info_mock)

        last = self.update_cluster_status_and_oswl_data(
            cls_id, consts.CLUSTER_STATUSES.error)
        # nothing is changed while cluster is in error status
        self.assertEqual(last.resource_data, res_data)

        last = self.update_cluster_status_and_oswl_data(
            cls_id, consts.CLUSTER_STATUSES.remove)
        removed = dict(self.vms_info[0])
        removed['time'] = last.updated_time.isoformat()
        res_data.update({
            'removed': [removed],
            'current': []})
        # current data is cleared when cluster status is changed
        self.assertEqual(last.resource_data, res_data)

    @patch('nailgun.statistics.oswl_collector.utils.ClientProvider')
    @patch('nailgun.statistics.oswl_collector.utils.get_proxy_for_cluster')
    @patch('nailgun.statistics.oswl_collector.utils.set_proxy')
    @patch('nailgun.statistics.oswl_collector.utils.'
           'get_info_from_os_resource_manager')
    def test_clear_data_for_removed_cluster(self, get_info_mock, *_):
        cls_id, res_data = self.collect_for_operational_cluster(get_info_mock)

        cls = Cluster.get_by_uid(cls_id)
        Cluster.delete(cls)

        oswl_collect_once(consts.OSWL_RESOURCE_TYPES.vm)
        last = OpenStackWorkloadStats.get_last_by(
            cls_id, consts.OSWL_RESOURCE_TYPES.vm)
        removed = dict(self.vms_info[0])
        removed['time'] = last.updated_time.isoformat()
        res_data.update({
            'removed': [removed],
            'current': []})
        # current data is cleared when cluster is deleted
        self.assertEqual(last.resource_data, res_data)

    @patch('nailgun.statistics.oswl_collector.utils.ClientProvider')
    @patch('nailgun.statistics.oswl_collector.utils.get_proxy_for_cluster')
    @patch('nailgun.statistics.oswl_collector.utils.set_proxy')
    @patch('nailgun.statistics.oswl_collector.utils.'
           'get_info_from_os_resource_manager')
    def test_removed_several_times(self, get_info_mock, *_):
        cls_id, res_data = self.collect_for_operational_cluster(get_info_mock)
        last = OpenStackWorkloadStats.get_last_by(
            cls_id, consts.OSWL_RESOURCE_TYPES.vm)
        self.assertItemsEqual(self.vms_info, last.resource_data['current'])

        # reset cluster
        get_info_mock.return_value = []
        oswl_collect_once(consts.OSWL_RESOURCE_TYPES.vm)
        last = OpenStackWorkloadStats.get_last_by(
            cls_id, consts.OSWL_RESOURCE_TYPES.vm)
        removed = dict(self.vms_info[0])
        removed['time'] = last.updated_time.isoformat()
        removed_data = [removed]
        # check data is not duplicated in removed on several collects
        for _ in xrange(10):
            oswl_collect_once(consts.OSWL_RESOURCE_TYPES.vm)
        last = OpenStackWorkloadStats.get_last_by(
            cls_id, consts.OSWL_RESOURCE_TYPES.vm)
        self.assertEqual(removed_data, last.resource_data['removed'])

        # cluster is operational
        # checking 'removed' is don't changed
        get_info_mock.return_value = self.vms_info
        oswl_collect_once(consts.OSWL_RESOURCE_TYPES.vm)
        last = OpenStackWorkloadStats.get_last_by(
            cls_id, consts.OSWL_RESOURCE_TYPES.vm)
        self.assertEqual(removed_data, last.resource_data['removed'])

        # reset cluster again
        # checking only id and time added to 'removed'
        get_info_mock.return_value = []
        oswl_collect_once(consts.OSWL_RESOURCE_TYPES.vm)
        last = OpenStackWorkloadStats.get_last_by(
            cls_id, consts.OSWL_RESOURCE_TYPES.vm)
        removed_data.append({
            'id': removed_data[0]['id'],
            'time': last.updated_time.isoformat()
        })
        self.assertListEqual(removed_data, last.resource_data['removed'])


class TestOSWLObject(BaseTestCase):

    def test_oswl_get_last_by_cluster_id_resource_type(self):
        cluster_id = 1
        dt = datetime.datetime.utcnow()
        obj_data = {
            'cluster_id': cluster_id,
            'resource_type': consts.OSWL_RESOURCE_TYPES.vm,

            'created_date': dt.date(),
            'updated_time': dt.time(),

            'resource_checksum': ""
        }
        obj = OpenStackWorkloadStats.create(obj_data)
        self.assertEqual(
            OpenStackWorkloadStats.get_last_by(
                cluster_id, consts.OSWL_RESOURCE_TYPES.vm),
            obj
        )
        self.assertIsNone(
            OpenStackWorkloadStats.get_last_by(
                0, consts.OSWL_RESOURCE_TYPES.vm)
        )
        self.assertIsNone(
            OpenStackWorkloadStats.get_last_by(
                cluster_id, consts.OSWL_RESOURCE_TYPES.tenant)
        )

        OpenStackWorkloadStats.delete(obj)
        self.assertIsNone(
            OpenStackWorkloadStats.get_last_by(
                cluster_id, consts.OSWL_RESOURCE_TYPES.vm)
        )

    def test_clean_expired_entries(self):
        dt_now = datetime.datetime.utcnow()
        t_delta = datetime.timedelta(days=settings.OSWL_STORING_PERIOD)

        entries_to_del_cluster_ids = (1, 2)
        for cluster_id in entries_to_del_cluster_ids:
            obj_kwargs = {
                "cluster_id": cluster_id,
                "resource_type": consts.OSWL_RESOURCE_TYPES.volume,
                "updated_time": dt_now.time(),
                "created_date": dt_now.date() - t_delta,
                "resource_checksum": ""
            }

            OpenStackWorkloadStats.create(obj_kwargs)

        untouched_obj_kwargs = {
            "cluster_id": 3,
            "resource_type": consts.OSWL_RESOURCE_TYPES.vm,
            "updated_time": dt_now.time(),
            "created_date": dt_now.date(),
            "resource_checksum": ""
        }
        OpenStackWorkloadStats.create(untouched_obj_kwargs)

        OpenStackWorkloadStatsCollection.clean_expired_entries()
        self.db.commit()

        for cluster_id in entries_to_del_cluster_ids:
            instance = \
                OpenStackWorkloadStats.get_last_by(
                    cluster_id,
                    consts.OSWL_RESOURCE_TYPES.volume
                )
            self.assertIsNone(instance)

        untouched_obj = OpenStackWorkloadStats.get_last_by(
            untouched_obj_kwargs["cluster_id"],
            consts.OSWL_RESOURCE_TYPES.vm
        )
        self.assertIsNotNone(untouched_obj)


class TestOSWLServerInfoSaving(BaseTestCase):

    vms_info = {
        "id": 1,
        "status": "running",
        "power_state": 1,
        "created_at": "dt",
        "host_id": "111",
        "tenant_id": "222",
        "image_id": "333",
        "flavor_id": "444"
    }

    @property
    def empty_data(self):
        return {
            'cluster_id': 1,
            'resource_type': consts.OSWL_RESOURCE_TYPES.vm,
            'created_date': datetime.datetime.utcnow().date(),

            'resource_data': {'added': [],
                              'removed': [],
                              'modified': [],
                              'current': []},
            'resource_checksum': oswl_data_checksum([]),
            'is_sent': False
        }

    def data_w_default_vm_info(self, time):
        data = self.empty_data
        data['resource_data'].update({
            'added': [{'time': time.isoformat(), 'id': 1}],
            'current': [self.vms_info]
        })
        return data

    def check_overall_rec_count(self, count):
        saved = OpenStackWorkloadStatsCollection.all()
        self.assertEqual(saved.count(), count)
        return saved

    def check_data_vs_rec(self, data, rec):
        data['resource_checksum'] = \
            oswl_data_checksum(data['resource_data']['current'])
        for k, v in six.iteritems(data):
            if isinstance(v, (list, tuple)):
                self.assertItemsEqual(v, getattr(rec, k))
            else:
                self.assertEqual(v, getattr(rec, k))

    def save_data_and_check_record(self, data):
        oswl_statistics_save(1, consts.OSWL_RESOURCE_TYPES.vm, data)
        last = OpenStackWorkloadStats.get_last_by(
            1, consts.OSWL_RESOURCE_TYPES.vm)
        self.assertEqual(last, self.check_overall_rec_count(1).first())
        return last

    def add_default_vm_info_and_check(self):
        last = self.save_data_and_check_record([self.vms_info])
        time_update = last.updated_time
        data = self.data_w_default_vm_info(time_update)
        self.check_data_vs_rec(data, last)
        return time_update, data

    def test_empty_data(self):
        last = self.save_data_and_check_record([])
        self.check_data_vs_rec(self.empty_data, last)

    def test_added_same_info(self):
        # VM is added
        time_update, data = self.add_default_vm_info_and_check()

        # save same info
        last = self.save_data_and_check_record([self.vms_info])
        # DB row was not updated
        self.assertEqual(time_update, last.updated_time)
        self.check_data_vs_rec(data, last)

    def test_added_one_by_one(self):
        # VM with id=1 is added
        time_update1, data = self.add_default_vm_info_and_check()

        # VM with id=2 is added
        two_vms = [dict(self.vms_info), dict(self.vms_info)]
        two_vms[1]['id'] = 2
        last = self.save_data_and_check_record(two_vms)

        time_update2 = last.updated_time
        data['resource_data'].update({
            'added': [{'time': time_update1.isoformat(), 'id': 1},
                      {'time': time_update2.isoformat(), 'id': 2}],
            'current': two_vms
        })
        self.check_data_vs_rec(data, last)

    def test_added_on_cluster_reset(self):
        # VM with id=1 is added
        time_update1, data = self.add_default_vm_info_and_check()

        # VM with id=2 is added
        two_vms = [self.vms_info]

        self.save_data_and_check_record(two_vms)
        # reset cluster
        self.save_data_and_check_record([])
        last = self.save_data_and_check_record(two_vms)

        time_update2 = last.updated_time
        time_removed2 = last.resource_data['removed'][0]['time']
        data['resource_data'].update({
            'added': [{'time': time_update1.isoformat(), 'id': 1},
                      {'time': time_update2.isoformat(), 'id': 1}],
            'current': two_vms,
            'removed': [dict(two_vms[0], **{'time': time_removed2})]
        })
        self.check_data_vs_rec(data, last)

    def test_added_then_removed(self):
        # VM is added
        time_update, data = self.add_default_vm_info_and_check()

        # VM is removed
        last = self.save_data_and_check_record([])

        time_update = last.updated_time
        removed = dict(self.vms_info)
        removed['time'] = time_update.isoformat()
        data['resource_data'].update({
            'removed': [removed],
            'current': []
        })
        self.check_data_vs_rec(data, last)

    def test_modified(self):
        # VM is added
        time_update, data = self.add_default_vm_info_and_check()

        # VM power state and status are changed
        vms_new = [dict(self.vms_info)]
        vms_new[0]['power_state'] = 0
        vms_new[0]['status'] = 'stopped'
        last = self.save_data_and_check_record(vms_new)

        time_update = last.updated_time
        modified1 = {'power_state': self.vms_info['power_state'],
                     'status': self.vms_info['status'],
                     'time': time_update.isoformat(),
                     'id': self.vms_info['id']}
        data['resource_data'].update({
            'modified': [modified1],
            'current': vms_new
        })
        self.check_data_vs_rec(data, last)

        # VM power state is changed back
        vms_new1 = [dict(vms_new[0])]
        vms_new1[0]['power_state'] = 1
        last = self.save_data_and_check_record(vms_new1)

        time_update = last.updated_time
        modified2 = {'power_state': vms_new[0]['power_state'],
                     'time': time_update.isoformat(),
                     'id': vms_new[0]['id']}
        data['resource_data'].update({
            'modified': [modified1, modified2],
            'current': vms_new1
        })
        self.check_data_vs_rec(data, last)

        # VM status is changed back
        last = self.save_data_and_check_record([self.vms_info])

        time_update = last.updated_time
        modified3 = {'status': vms_new1[0]['status'],
                     'time': time_update.isoformat(),
                     'id': vms_new1[0]['id']}
        data['resource_data'].update({
            'modified': [modified1, modified2, modified3],
            'current': [self.vms_info]
        })
        self.check_data_vs_rec(data, last)

    def test_add_row_per_day(self):
        # VM is added
        last = self.save_data_and_check_record([self.vms_info])

        date_cur = last.created_date
        time_update = last.updated_time
        date_1st_rec = date_cur - datetime.timedelta(days=1)
        # make existing record one day older
        OpenStackWorkloadStats.update(last,
                                      {'created_date': date_1st_rec})

        # pass the same data
        # no new record was created and existing one remains unchanged
        self.assertEqual(last,
                         self.save_data_and_check_record([self.vms_info]))

        # VM is removed
        oswl_statistics_save(1, consts.OSWL_RESOURCE_TYPES.vm, [])
        saved = self.check_overall_rec_count(2)
        last = OpenStackWorkloadStats.get_last_by(
            1, consts.OSWL_RESOURCE_TYPES.vm)

        self.assertEqual(last.created_date, date_cur)
        for rec in saved:
            if rec.created_date == date_cur:
                self.assertEqual(rec, last)
                # last record contains 'removed' and empty 'added'
                data = self.empty_data
                removed = dict(self.vms_info)
                removed['time'] = last.updated_time.isoformat()
                data['resource_data']['removed'] = [removed]
                self.check_data_vs_rec(data, rec)
            elif rec.created_date == date_1st_rec:
                # first record contains 'added' and empty 'removed'
                data = self.data_w_default_vm_info(time_update)
                data['created_date'] = date_1st_rec
                self.check_data_vs_rec(data, rec)

    def test_oswl_is_sent_restored_on_changes(self):
        cluster_id = 1
        vm_info = {
            "id": 1,
            "power_state": 1,
        }
        oswl_statistics_save(cluster_id, consts.OSWL_RESOURCE_TYPES.vm,
                             [vm_info])
        last = OpenStackWorkloadStats.get_last_by(
            cluster_id, consts.OSWL_RESOURCE_TYPES.vm)
        # Setting is_sent to True
        OpenStackWorkloadStats.update(last, {'is_sent': True})
        self.assertEqual(True, last.is_sent)

        # Checking is_sent is not changed if data is not changed
        oswl_statistics_save(cluster_id, consts.OSWL_RESOURCE_TYPES.vm,
                             [vm_info])
        last_no_change = OpenStackWorkloadStats.get_last_by(
            cluster_id, consts.OSWL_RESOURCE_TYPES.vm)
        self.assertEqual(True, last_no_change.is_sent)

        # Checking is_sent is changed if data is changed
        vm_info["power_state"] += 1
        oswl_statistics_save(cluster_id, consts.OSWL_RESOURCE_TYPES.vm,
                             [vm_info])
        last_changed = OpenStackWorkloadStats.get_last_by(
            cluster_id, consts.OSWL_RESOURCE_TYPES.vm)
        self.assertEqual(False, last_changed.is_sent)
