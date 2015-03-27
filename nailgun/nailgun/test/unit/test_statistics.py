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
import six
from sqlalchemy.inspection import inspect
import urllib3

from nailgun.test.base import BaseTestCase

from nailgun import consts
from nailgun.db.sqlalchemy.models import cluster as cluster_model
from nailgun.db.sqlalchemy.models import plugins
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
        attrs_dict = info.get_attributes(editable, info.attributes_white_list)
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
        attrs_dict = info.get_attributes(editable, info.attributes_white_list)
        self.assertEqual(
            # no vlan splinters for ubuntu
            set(attr_key_list) - set(
                ('vlan_splinters', 'vlan_splinters_ovs', 'vswitch')),
            set(attrs_dict.keys())
        )

    def test_get_attributes(self):
        attributes = {
            'a': 'b',
            'c': [
                {'x': 'z', 'y': [{'t': 'u'}, {'v': 'w'}, {'t': 'u0'}]},
                {'x': 'zz', 'y': [{'t': 'uu'}, {'v': 'ww'}]}
            ],
            'd': {'f': 'g', 'k': [0, 1, 2]},
        }
        white_list = (
            (('a',), 'map_a', None),
            (('d', 'f'), 'map_f', None),
            (('d', 'k'), 'map_k_len', len),
            (('c', 'x'), 'map_x', None),
            (('c', 'y', 't'), 'map_t', None),
        )

        info = InstallationInfo()
        actual = info.get_attributes(attributes, white_list)
        expected = {
            'map_f': 'g',
            'map_k_len': 3,
            'map_a': 'b',
            'map_x': ['z', 'zz'],
            'map_t': [['u', 'u0'], ['uu']],
        }
        self.assertDictEqual(actual, expected)

    def test_get_empty_attributes(self):
        info = InstallationInfo()
        trash_attrs = {'some': 'trash', 'nested': {'n': 't'}}
        result = info.get_attributes(trash_attrs, info.attributes_white_list)
        self.assertDictEqual({}, result)

    def test_get_attributes_exception_handled(self):
        info = InstallationInfo()
        variants = [
            None,
            {},
            {'common': None},
            {'common': {'libvirt_type': {}}},
            {'common': {'libvirt_type': 3}},
        ]
        for attrs in variants:
            result = info.get_attributes(attrs, info.attributes_white_list)
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
        self.env.create(cluster_kwargs={
            'mode': consts.CLUSTER_MODES.ha_full,
            'net_provider': consts.CLUSTER_NET_PROVIDERS.nova_network
        })
        clusters_info = info.get_clusters_info()
        cluster_info = clusters_info[0]
        self.assertTrue('network_configuration' in cluster_info)
        network_config = cluster_info['network_configuration']

        for field in ('fixed_network_size', 'fixed_networks_vlan_start',
                      'fixed_networks_amount', 'net_manager'):
            self.assertIn(field, network_config)

        # Checking neutron network configuration
        self.env.create(cluster_kwargs={
            'mode': consts.CLUSTER_MODES.ha_full,
            'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron
        })
        clusters_info = info.get_clusters_info()
        cluster_info = clusters_info[1]
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

    def test_all_cluster_data_collected(self):
        self.env.create(nodes_kwargs=[{'roles': ['compute']}])
        self.env.create_node(status=consts.NODE_STATUSES.discover)

        # Fetching installation info struct
        info = InstallationInfo()
        info = info.get_installation_info()
        actual_cluster = info['clusters'][0]

        # Creating cluster schema
        cluster_schema = {}
        for column in inspect(cluster_model.Cluster).columns:
            cluster_schema[six.text_type(column.name)] = None
        for rel in inspect(cluster_model.Cluster).relationships:
            cluster_schema[six.text_type(rel.table.name)] = None

        # Removing of not required fields
        remove_fields = (
            'tasks', 'cluster_changes', 'nodegroups', 'pending_release_id',
            'releases', 'replaced_provisioning_info', 'notifications',
            'deployment_tasks', 'name', 'replaced_deployment_info',
            'grouping'
        )
        for field in remove_fields:
            cluster_schema.pop(field, None)
        # Renaming fields for matching
        rename_fields = (
            ('plugins', 'installed_plugins'),
            ('networking_configs', 'network_configuration'),
            ('release_id', 'release'),
        )
        for name_from, name_to in rename_fields:
            cluster_schema.pop(name_from)
            cluster_schema[name_to] = None

        # If test failed here it means, that you have added properties
        # to cluster and they are not exported into statistics.
        # If you don't know  what to do, contact fuel-stats team please.
        for key in six.iterkeys(cluster_schema):
            self.assertIn(key, actual_cluster)

    def _find_leafs_paths(self, structure, leafs_names=('value',)):
        """Finds paths to leafs
        :param structure: structure for searching
        :param leafs_names: leafs names
        :return: list of tuples of dicts keys to leafs
        """

        def _keys_paths_helper(result, keys, struct):
            if isinstance(struct, dict):
                for k in sorted(six.iterkeys(struct)):
                    if k in leafs_names:
                        result.append(keys)
                    else:
                        _keys_paths_helper(result, keys + (k,), struct[k])
            elif isinstance(struct, (tuple, list)):
                for d in struct:
                    _keys_paths_helper(result, keys, d)
            else:
                # leaf not found
                pass
        leafs_paths = []
        _keys_paths_helper(leafs_paths, (), structure)
        return self._remove_private_leafs_paths(leafs_paths)

    def _remove_private_leafs_paths(self, leafs_paths):
        """Removes paths to private information
        :return: leafs paths without paths to private information
        """
        private_paths = (
            ('access', 'email'), ('access', 'password'), ('access', 'tenant'),
            ('access', 'user'), ('common', 'auth_key'), ('corosync', 'group'),
            ('corosync', 'port'), ('external_dns', 'dns_list'),
            ('external_mongo', 'hosts_ip'),
            ('external_mongo', 'mongo_db_name'),
            ('external_mongo', 'mongo_password'),
            ('external_mongo', 'mongo_user'), ('syslog', 'syslog_port'),
            ('syslog', 'syslog_server'), ('workloads_collector', 'password'),
            ('workloads_collector', 'tenant'),
            ('workloads_collector', 'username'), ('zabbix', 'password'),
            ('zabbix', 'username'), ('nsx_plugin', 'l3_gw_service_uuid'),
            ('nsx_plugin', 'nsx_controllers'), ('nsx_plugin', 'nsx_password'),
            ('nsx_plugin', 'nsx_username'),
            ('nsx_plugin', 'transport_zone_uuid'),
            ('storage', 'vc_datacenter'), ('storage', 'vc_datastore'),
            ('storage', 'volumes_vmdk'), ('storage', 'vc_host'),
            ('storage', 'vc_image_dir'), ('storage', 'vc_password'),
            ('storage', 'vc_user'),
            ('vcenter', 'cluster'), ('vcenter', 'datastore_regex'),
            ('vcenter', 'host_ip'), ('vcenter', 'vc_password'),
            ('vcenter', 'vc_user'), ('vcenter', 'vlan_interface'),
            ('vcenter', 'vlan_interface')
        )
        return filter(lambda x: x not in private_paths, leafs_paths)

    def test_all_cluster_attributes_in_white_list(self):
        self.env.create(nodes_kwargs=[{'roles': ['compute']}])
        self.env.create_node(status=consts.NODE_STATUSES.discover)

        cluster = self.env.clusters[0]
        expected_paths = self._find_leafs_paths(cluster.attributes.editable)

        # Removing 'value' from expected paths
        actual_paths = [rule.path[:-1] for rule in
                        InstallationInfo.attributes_white_list]
        # If test failed here it means, that you have added cluster
        # attributes and they are not added into
        # InstallationInfo.attributes_white_list
        # If you don't know what should be added into white list, contact
        # fuel-stats team please.
        for path in expected_paths:
            self.assertIn(path, actual_paths)

    def test_wite_list_unique_names(self):
        names = set(rule.map_to_name for rule in
                    InstallationInfo.attributes_white_list)
        self.assertEqual(len(InstallationInfo.attributes_white_list),
                         len(names))


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
