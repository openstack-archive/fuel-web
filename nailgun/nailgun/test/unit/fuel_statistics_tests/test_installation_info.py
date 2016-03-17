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
import six
from sqlalchemy.inspection import inspect

from nailgun.test.base import BaseTestCase

from nailgun import consts
from nailgun.db.sqlalchemy.models import cluster as cluster_model
from nailgun.db.sqlalchemy.models import plugins
from nailgun.objects import Cluster
from nailgun.objects import ReleaseCollection
from nailgun.objects import VmwareAttributes
from nailgun.settings import settings
from nailgun.statistics.fuel_statistics.installation_info \
    import InstallationInfo


class TestInstallationInfo(BaseTestCase):

    def setUp(self):
        self.patcher = mock.patch(
            'nailgun.statistics.fuel_statistics.installation_info'
            '.InstallationInfo.fuel_packages_info', return_value=[])
        self.patcher.start()
        super(TestInstallationInfo, self).setUp()

    def tearDown(self):
        super(TestInstallationInfo, self).tearDown()
        self.patcher.stop()

    def test_release_info(self):
        info = InstallationInfo()
        f_info = info.fuel_release_info()
        self.assertDictEqual(f_info, settings.VERSION)

    def test_get_attributes_centos(self):
        self.skipTest('CentOS is unavailable in current release.')
        release_name = 'CentOS'
        info = InstallationInfo()
        attr_key_list = [a[1] for a in info.attributes_white_list]
        # No UCA configs for CentOS.
        expected_attributes = set(attr_key_list) - set(
            ('pin_haproxy', 'repo_type', 'pin_ceph', 'pin_rabbitmq'))
        self._do_test_attributes_in_white_list(
            release_name, expected_attributes)

    def _do_test_attributes_in_white_list(self, release_name,
                                          expected_attributes):
        self.env.upload_fixtures(['openstack'])

        releases = ReleaseCollection.filter_by(
            None, name=release_name)
        cluster_data = self.env.create_cluster(
            release_id=releases[0].id
        )
        cluster = Cluster.get_by_uid(cluster_data['id'])
        editable = cluster.attributes.editable

        info = InstallationInfo()
        actual_attributes = info.get_attributes(
            editable, info.attributes_white_list)
        self.assertEqual(
            set(expected_attributes),
            set(actual_attributes.keys())
        )

    def test_get_attributes_ubuntu(self):
        release_name = 'Liberty on Ubuntu 14.04'
        info = InstallationInfo()
        attr_key_list = [a[1] for a in info.attributes_white_list]
        # No vlan splinters for Ubuntu, no mellanox related entries
        # since 8.0, no UCA repos settings.
        expected_attributes = set(attr_key_list) - set(
            ('vlan_splinters', 'vlan_splinters_ovs',
             'mellanox', 'mellanox_vf_num', 'iser', 'pin_haproxy',
             'repo_type', 'pin_ceph', 'pin_rabbitmq'))
        self._do_test_attributes_in_white_list(
            release_name, expected_attributes)

    def test_get_attributes_ubuntu_uca(self):
        release_name = 'Liberty on Ubuntu+UCA 14.04'
        info = InstallationInfo()
        attr_key_list = [a[1] for a in info.attributes_white_list]
        # No vlan splinters for Ubuntu, no mellanox related entries
        # since 8.0.
        expected_attributes = set(attr_key_list) - set(
            ('vlan_splinters', 'vlan_splinters_ovs',
             'mellanox', 'mellanox_vf_num', 'iser'))
        self._do_test_attributes_in_white_list(
            release_name, expected_attributes)

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

    def test_clusters_info_no_vmware_attributes_exception(self):
        self.env.upload_fixtures(['openstack'])
        info = InstallationInfo()
        release = ReleaseCollection.filter_by(
            None, operating_system=consts.RELEASE_OS.ubuntu)
        nodes_params = [
            {'roles': ['compute']},
            {'roles': ['compute']},
            {'roles': ['controller']}
        ]
        self.env.create(
            cluster_kwargs={
                'release_id': release[0].id,
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron},
            nodes_kwargs=nodes_params
        )
        self.env.create_node({'status': consts.NODE_STATUSES.discover})
        cluster = self.env.clusters[0]
        VmwareAttributes.delete(cluster.vmware_attributes)
        self.env.db.flush()
        self.assertNotRaises(AttributeError, info.get_clusters_info)

    def test_clusters_info(self):
        self.env.upload_fixtures(['openstack'])
        info = InstallationInfo()
        release = ReleaseCollection.filter_by(
            None, operating_system=consts.RELEASE_OS.ubuntu)
        nodes_params = [
            {'roles': ['compute']},
            {'roles': ['compute']},
            {'roles': ['controller']}
        ]
        self.env.create(
            cluster_kwargs={
                'release_id': release[0].id,
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron},
            nodes_kwargs=nodes_params
        )
        self.env.create_node({'status': consts.NODE_STATUSES.discover})
        clusters_info = info.get_clusters_info()
        cluster = self.env.clusters[0]
        self.assertEquals(1, len(clusters_info))
        cluster_info = clusters_info[0]

        self.assertEquals(len(nodes_params), len(cluster_info['nodes']))
        self.assertEquals(len(nodes_params), cluster_info['nodes_num'])

        self.assertEquals(consts.CLUSTER_MODES.ha_compact,
                          cluster_info['mode'])
        self.assertEquals(consts.CLUSTER_NET_PROVIDERS.neutron,
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
            'mode': consts.CLUSTER_MODES.ha_compact,
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
            'mode': consts.CLUSTER_MODES.ha_compact,
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
        cluster = self.env.create(
            release_kwargs={
                'operating_system': consts.RELEASE_OS.centos
            })
        self.env.create_nodes_w_interfaces_count(
            nodes_count=2,
            if_count=4,
            roles=['controller', 'compute'],
            pending_addition=True,
            cluster_id=cluster['id'])

        self.env.make_bond_via_api(
            'bond0', consts.BOND_MODES.active_backup,
            ['eth1', 'eth2'], node_id=self.env.nodes[0].id)
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

            self.assertIn('meta', node_info)
            for iface in node_info['meta']['interfaces']:
                self.assertNotIn('mac', iface)
            self.assertNotIn('fqdn', node_info['meta']['system'])
            self.assertNotIn('serial', node_info['meta']['system'])

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
        cluster = self.env.create_cluster(api=False)
        plugin = self.env.create_plugin(api=False, cluster=cluster)

        plugin_kwargs = self.env.get_default_plugin_metadata()
        plugin_kwargs['id'] = plugin.id

        for name, expected in six.iteritems(plugin_kwargs):
            actual = getattr(plugin, name)
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
            'tasks', 'cluster_changes', 'nodegroups',
            'releases', 'replaced_provisioning_info', 'notifications',
            'cluster_deployment_graphs', 'name', 'replaced_deployment_info',
            'ui_settings'
        )
        for field in remove_fields:
            cluster_schema.pop(field)
        # Renaming fields for matching
        rename_fields = (
            ('plugins', 'installed_plugins'),
            ('networking_configs', 'network_configuration'),
            ('release_id', 'release'),
            ('cluster_plugin_links', 'plugin_links'),
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
            ('workloads_collector', 'user'), ('zabbix', 'password'),
            ('zabbix', 'username'),
            ('common', 'use_vcenter'),  # removed attribute
            ('murano_settings', 'murano_repo_url'),
            ('use_fedora_lt', 'kernel'),
            ('public_ssl', 'cert_data'), ('public_ssl', 'hostname'),
            ('operator_user', 'name'),
            ('operator_user', 'password'),
            ('operator_user', 'homedir'),
            ('operator_user', 'authkeys'),
            ('operator_user', 'sudo'),
            ('service_user', 'name'),
            ('service_user', 'sudo'),
            ('service_user', 'homedir'),
            ('service_user', 'password'),
            ('service_user', 'root_password'),
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

    def test_all_cluster_vmware_attributes_in_white_list(self):
        self.env.create(nodes_kwargs=[{'roles': ['compute']}])
        self.env.create_node(status=consts.NODE_STATUSES.discover)

        cluster = self.env.clusters[0]
        expected_paths = self._find_leafs_paths(
            cluster.vmware_attributes.editable,
            leafs_names=('vsphere_cluster', 'enable'))

        # Removing leaf name from expected paths
        actual_paths = [rule.path[:-1] for rule in
                        InstallationInfo.vmware_attributes_white_list]
        # If test failed here it means, that you have added cluster vmware
        # attributes and they are not added into
        # InstallationInfo.vmware_attributes_white_list
        # If you don't know what should be added into white list, contact
        # fuel-stats team please.
        for path in expected_paths:
            self.assertIn(path, actual_paths)

    def test_all_plugin_data_collected(self):
        cluster = self.env.create_cluster(api=False)
        self.env.create_plugin(api=False, cluster=cluster)

        # Fetching plugin info
        info = InstallationInfo().get_cluster_plugins_info(cluster)
        actual_plugin = info[0]

        # Creating plugin data schema
        plugin_schema = {}
        for column in inspect(plugins.Plugin).columns:
            plugin_schema[six.text_type(column.name)] = None

        # Removing of not required fields
        remove_fields = ('description', 'title', 'authors', 'homepage')
        for field in remove_fields:
            plugin_schema.pop(field)

        # If test failed here it means, that you have added properties
        # to plugin and they are not exported into statistics.
        # If you don't know what to do, contact fuel-stats team please.
        for key in six.iterkeys(plugin_schema):
            self.assertIn(key, actual_plugin)

    def test_wite_list_unique_names(self):
        names = set(rule.map_to_name for rule in
                    InstallationInfo.attributes_white_list)
        self.assertEqual(len(InstallationInfo.attributes_white_list),
                         len(names))
        names = set(rule.map_to_name for rule in
                    InstallationInfo.vmware_attributes_white_list)
        self.assertEqual(len(InstallationInfo.vmware_attributes_white_list),
                         len(names))
        names = set(rule.map_to_name for rule in
                    InstallationInfo.plugin_info_white_list)
        self.assertEqual(len(InstallationInfo.plugin_info_white_list),
                         len(names))
