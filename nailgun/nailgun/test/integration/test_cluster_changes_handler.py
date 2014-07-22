# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

from copy import deepcopy
from itertools import izip
from mock import patch
import netaddr

import nailgun

from nailgun import objects

from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.network.manager import NetworkManager
from nailgun.openstack.common import jsonutils
from nailgun.settings import settings
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse
from nailgun.volumes import manager


class TestHandlers(BaseIntegrationTest):

    def tearDown(self):
        self._wait_for_threads()
        super(TestHandlers, self).tearDown()

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_nova_deploy_cast_with_right_args(self, mocked_rpc):
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['controller', 'cinder'], 'pending_addition': True},
                {'roles': ['compute', 'cinder'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True},
                {'roles': ['cinder'], 'pending_addition': True}
            ]
        )

        cluster_db = self.env.clusters[0]

        common_attrs = {
            'deployment_mode': 'ha_compact',

            'management_vip': '192.168.0.1',
            'public_vip': '172.16.0.2',

            'fixed_network_range': '10.0.0.0/16',
            'management_network_range': '192.168.0.0/24',
            'floating_network_range': ['172.16.0.128-172.16.0.254'],
            'storage_network_range': '192.168.1.0/24',

            'mp': [{'weight': '1', 'point': '1'},
                   {'weight': '2', 'point': '2'}],
            'novanetwork_parameters': {
                'network_manager': 'FlatDHCPManager',
                'network_size': 256
            },
            'dns_nameservers': [
                "8.8.4.4",
                "8.8.8.8"
            ],

            'management_interface': 'eth0.101',
            'fixed_interface': 'eth0.103',
            'admin_interface': 'eth1',
            'storage_interface': 'eth0.102',
            'public_interface': 'eth0',
            'floating_interface': 'eth0',

            'master_ip': '127.0.0.1',
            'use_cinder': True,
            'deployment_id': cluster_db.id,
            'openstack_version': cluster_db.release.version,
            'fuel_version': cluster_db.fuel_version
        }
        common_attrs.update(
            objects.Release.get_orchestrator_data_dict(cluster_db.release)
        )

        cluster_attrs = objects.Attributes.merged_attrs_values(
            cluster_db.attributes
        )
        common_attrs.update(cluster_attrs)

        # Common attrs calculation
        nodes_list = []
        nodes_db = sorted(cluster_db.nodes, key=lambda n: n.id)
        assigned_ips = {}
        i = 0
        admin_ips = [
            '10.20.0.134/24',
            '10.20.0.133/24',
            '10.20.0.132/24',
            '10.20.0.131/24',
            '10.20.0.130/24',
            '10.20.0.129/24']
        for node in nodes_db:
            node_id = node.id
            admin_ip = admin_ips.pop()
            for role in sorted(node.roles + node.pending_roles):
                assigned_ips[node_id] = {}
                assigned_ips[node_id]['internal'] = '192.168.0.%d' % (i + 2)
                assigned_ips[node_id]['public'] = '172.16.0.%d' % (i + 3)
                assigned_ips[node_id]['storage'] = '192.168.1.%d' % (i + 1)
                assigned_ips[node_id]['admin'] = admin_ip

                nodes_list.append({
                    'role': role,

                    'internal_address': assigned_ips[node_id]['internal'],
                    'public_address': assigned_ips[node_id]['public'],
                    'storage_address': assigned_ips[node_id]['storage'],

                    'internal_netmask': '255.255.255.0',
                    'public_netmask': '255.255.255.0',
                    'storage_netmask': '255.255.255.0',

                    'uid': str(node_id),
                    'swift_zone': str(node_id),

                    'name': 'node-%d' % node_id,
                    'fqdn': 'node-%d.%s' % (node_id, settings.DNS_DOMAIN)})
            i += 1

        controller_nodes = filter(
            lambda node: node['role'] == 'controller',
            deepcopy(nodes_list))

        common_attrs['nodes'] = nodes_list
        common_attrs['nodes'][0]['role'] = 'primary-controller'

        common_attrs['last_controller'] = controller_nodes[-1]['name']
        common_attrs['storage']['pg_num'] = 128

        common_attrs['test_vm_image'] = {
            'container_format': 'bare',
            'public': 'true',
            'disk_format': 'qcow2',
            'img_name': 'TestVM',
            'img_path': '/opt/vm/cirros-x86_64-disk.img',
            'os_name': 'cirros',
            'min_ram': 64,
            'glance_properties': (
                """--property murano_image_info="""
                """'{"title": "Murano Demo", "type": "cirros.demo"}'"""
            ),
        }

        # Individual attrs calculation and
        # merging with common attrs
        priority_mapping = {
            'controller': [600, 600, 500],
            'cinder': 700,
            'compute': 700
        }

        critical_mapping = {
            'primary-controller': True,
            'controller': False,
            'cinder': False,
            'compute': False
        }

        deployment_info = []
        for node in nodes_db:
            ips = assigned_ips[node.id]
            for role in sorted(node.roles):
                priority = priority_mapping[role]
                is_critical = critical_mapping[role]
                if isinstance(priority, list):
                    priority = priority.pop()

                individual_atts = {
                    'uid': str(node.id),
                    'status': node.status,
                    'role': role,
                    'online': node.online,
                    'fail_if_error': is_critical,
                    'fqdn': 'node-%d.%s' % (node.id, settings.DNS_DOMAIN),
                    'priority': priority,

                    'network_data': {
                        'eth0': {
                            'interface': 'eth0',
                            'ipaddr': ['%s/24' % ips['public']],
                            'gateway': '172.16.0.1'},
                        'eth0.101': {
                            'interface': 'eth0.101',
                            'ipaddr': ['%s/24' % ips['internal']]},
                        'eth0.102': {
                            'interface': 'eth0.102',
                            'ipaddr': ['%s/24' % ips['storage']]},
                        'eth0.103': {
                            'interface': 'eth0.103',
                            'ipaddr': 'none'},
                        'lo': {
                            'interface': 'lo',
                            'ipaddr': ['127.0.0.1/8']},
                        'eth1': {
                            'interface': 'eth1',
                            'ipaddr': [ips['admin']]}
                    }}

                individual_atts.update(common_attrs)
                individual_atts['glance']['image_cache_max_size'] = str(
                    manager.calc_glance_cache_size(node.attributes.volumes)
                )
                deployment_info.append(deepcopy(individual_atts))

        controller_nodes = filter(
            lambda node: node['role'] == 'controller',
            deployment_info)
        controller_nodes[0]['role'] = 'primary-controller'
        controller_nodes[0]['fail_if_error'] = True

        supertask = self.env.launch_deployment()
        deploy_task_uuid = [x.uuid for x in supertask.subtasks
                            if x.name == 'deployment'][0]

        deployment_msg = {
            'api_version': '1',
            'method': 'deploy',
            'respond_to': 'deploy_resp',
            'args': {}
        }

        deployment_msg['args']['task_uuid'] = deploy_task_uuid
        deployment_msg['args']['deployment_info'] = deployment_info

        provision_nodes = []
        admin_net = self.env.network_manager.get_admin_network_group()

        for n in sorted(self.env.nodes, key=lambda n: n.id):
            udev_interfaces_mapping = ','.join([
                '{0}_{1}'.format(i.mac, i.name) for i in n.interfaces])
            eth1_mac = [i.mac for i in n.interfaces if i.name == 'eth1'][0]

            pnd = {
                'profile': cluster_attrs['cobbler']['profile'],
                'power_type': 'ssh',
                'power_user': 'root',
                'kernel_options': {
                    'netcfg/choose_interface': eth1_mac,
                    'udevrules': udev_interfaces_mapping},
                'power_address': n.ip,
                'power_pass': settings.PATH_TO_BOOTSTRAP_SSH_KEY,
                'name': objects.Node.make_slave_name(n),
                'hostname': n.fqdn,
                'name_servers': '\"%s\"' % settings.DNS_SERVERS,
                'name_servers_search': '\"%s\"' % settings.DNS_SEARCH,
                'netboot_enabled': '1',
                'ks_meta': {
                    'fuel_version': cluster_db.fuel_version,
                    'puppet_auto_setup': 1,
                    'puppet_master': settings.PUPPET_MASTER_HOST,
                    'puppet_enable': 0,
                    'mco_auto_setup': 1,
                    'install_log_2_syslog': 1,
                    'mco_pskey': settings.MCO_PSKEY,
                    'mco_vhost': settings.MCO_VHOST,
                    'mco_host': settings.MCO_HOST,
                    'mco_user': settings.MCO_USER,
                    'mco_password': settings.MCO_PASSWORD,
                    'mco_connector': settings.MCO_CONNECTOR,
                    'mco_enable': 1,
                    'pm_data': {
                        'ks_spaces': n.attributes.volumes,
                        'kernel_params': objects.Node.get_kernel_params(n),
                    },
                    'auth_key': "\"%s\"" % cluster_attrs.get('auth_key', ''),
                    'mlnx_vf_num': "16",
                    'mlnx_plugin_mode': "disabled",
                    'mlnx_iser_enabled': False,
                }
            }
            orchestrator_data = objects.Release.get_orchestrator_data_dict(
                cluster_db.release)
            if orchestrator_data:
                pnd['ks_meta']['repo_metadata'] = \
                    orchestrator_data['repo_metadata']

            vlan_splinters = cluster_attrs.get('vlan_splinters', None)
            if vlan_splinters == 'kernel_lt':
                pnd['ks_meta']['kernel_lt'] = 1

            NetworkManager.assign_admin_ips(n.id, 1)

            admin_ip = self.env.network_manager.get_admin_ip_for_node(n)

            for i in n.interfaces:
                if 'interfaces' not in pnd:
                    pnd['interfaces'] = {}
                pnd['interfaces'][i.name] = {
                    'mac_address': i.mac,
                    'static': '0',
                }
                if 'interfaces_extra' not in pnd:
                    pnd['interfaces_extra'] = {}
                pnd['interfaces_extra'][i.name] = {
                    'peerdns': 'no',
                    'onboot': 'no'
                }

                if i.mac == n.mac:
                    pnd['interfaces'][i.name]['dns_name'] = n.fqdn
                    pnd['interfaces_extra'][i.name]['onboot'] = 'yes'
                    pnd['interfaces'][i.name]['ip_address'] = admin_ip
                    pnd['interfaces'][i.name]['netmask'] = str(
                        netaddr.IPNetwork(admin_net.cidr).netmask)

            provision_nodes.append(pnd)

        provision_task_uuid = filter(
            lambda t: t.name == 'provision',
            supertask.subtasks)[0].uuid

        provision_msg = {
            'api_version': '1',
            'method': 'provision',
            'respond_to': 'provision_resp',
            'args': {
                'task_uuid': provision_task_uuid,
                'provisioning_info': {
                    'engine': {
                        'url': settings.COBBLER_URL,
                        'username': settings.COBBLER_USER,
                        'password': settings.COBBLER_PASSWORD,
                        'master_ip': settings.MASTER_IP},
                    'nodes': provision_nodes}}}

        args, kwargs = nailgun.task.manager.rpc.cast.call_args
        self.assertEqual(len(args), 2)
        self.assertEqual(len(args[1]), 2)

        self.datadiff(args[1][0], provision_msg)
        self.datadiff(args[1][1], deployment_msg)

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_neutron_deploy_cast_with_right_args(self, mocked_rpc):
        self.env.create(
            cluster_kwargs={
                'net_provider': 'neutron',
                'net_segment_type': 'gre'
            },
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['controller', 'cinder'], 'pending_addition': True},
                {'roles': ['compute', 'cinder'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True},
                {'roles': ['cinder'], 'pending_addition': True}
            ]
        )

        cluster_db = self.env.clusters[0]

        common_attrs = {
            'deployment_mode': 'ha_compact',

            'management_vip': '192.168.0.1',
            'public_vip': '172.16.0.2',

            'management_network_range': '192.168.0.0/24',
            'storage_network_range': '192.168.1.0/24',

            'mp': [{'weight': '1', 'point': '1'},
                   {'weight': '2', 'point': '2'}],

            'quantum': True,
            'quantum_settings': {},

            'master_ip': '127.0.0.1',
            'use_cinder': True,
            'deployment_id': cluster_db.id,
            'openstack_version': cluster_db.release.version,
            'fuel_version': cluster_db.fuel_version
        }
        common_attrs.update(
            objects.Release.get_orchestrator_data_dict(cluster_db.release)
        )

        cluster_attrs = objects.Attributes.merged_attrs_values(
            cluster_db.attributes
        )
        common_attrs.update(cluster_attrs)

        L2 = {
            "base_mac": "fa:16:3e:00:00:00",
            "segmentation_type": "gre",
            "phys_nets": {
                "physnet1": {
                    "bridge": "br-ex",
                    "vlan_range": None}
            },
            "tunnel_id_ranges": "2:65535"
        }
        L3 = {
            "use_namespaces": True
        }
        predefined_networks = {
            "net04_ext": {
                'shared': False,
                'L2': {
                    'router_ext': True,
                    'network_type': 'flat',
                    'physnet': 'physnet1',
                    'segment_id': None},
                'L3': {
                    'subnet': u'172.16.0.0/24',
                    'enable_dhcp': False,
                    'nameservers': [],
                    'floating': '172.16.0.130:172.16.0.254',
                    'gateway': '172.16.0.1'},
                'tenant': 'admin'
            },
            "net04": {
                'shared': False,
                'L2': {
                    'router_ext': False,
                    'network_type': 'gre',
                    'physnet': None,
                    'segment_id': None},
                'L3': {
                    'subnet': u'192.168.111.0/24',
                    'enable_dhcp': True,
                    'nameservers': [
                        '8.8.4.4',
                        '8.8.8.8'],
                    'floating': None,
                    'gateway': '192.168.111.1'},
                'tenant': 'admin'
            }
        }
        common_attrs['quantum_settings'].update(
            L2=L2,
            L3=L3,
            predefined_networks=predefined_networks)

        # Common attrs calculation
        nodes_list = []
        nodes_db = sorted(cluster_db.nodes, key=lambda n: n.id)
        assigned_ips = {}
        i = 0
        admin_ips = [
            '10.20.0.134/24',
            '10.20.0.133/24',
            '10.20.0.132/24',
            '10.20.0.131/24',
            '10.20.0.130/24',
            '10.20.0.129/24']
        for node in nodes_db:
            node_id = node.id
            admin_ip = admin_ips.pop()
            for role in sorted(node.roles + node.pending_roles):
                assigned_ips[node_id] = {}
                assigned_ips[node_id]['management'] = '192.168.0.%d' % (i + 2)
                assigned_ips[node_id]['public'] = '172.16.0.%d' % (i + 3)
                assigned_ips[node_id]['storage'] = '192.168.1.%d' % (i + 1)
                assigned_ips[node_id]['admin'] = admin_ip

                nodes_list.append({
                    'role': role,

                    'internal_address': assigned_ips[node_id]['management'],
                    'public_address': assigned_ips[node_id]['public'],
                    'storage_address': assigned_ips[node_id]['storage'],

                    'internal_netmask': '255.255.255.0',
                    'public_netmask': '255.255.255.0',
                    'storage_netmask': '255.255.255.0',

                    'uid': str(node_id),
                    'swift_zone': str(node_id),

                    'name': 'node-%d' % node_id,
                    'fqdn': 'node-%d.%s' % (node_id, settings.DNS_DOMAIN)})
            i += 1

        controller_nodes = filter(
            lambda node: node['role'] == 'controller',
            deepcopy(nodes_list))

        common_attrs['nodes'] = nodes_list
        common_attrs['nodes'][0]['role'] = 'primary-controller'

        common_attrs['last_controller'] = controller_nodes[-1]['name']
        common_attrs['storage']['pg_num'] = 128

        common_attrs['test_vm_image'] = {
            'container_format': 'bare',
            'public': 'true',
            'disk_format': 'qcow2',
            'img_name': 'TestVM',
            'img_path': '/opt/vm/cirros-x86_64-disk.img',
            'os_name': 'cirros',
            'min_ram': 64,
            'glance_properties': (
                """--property murano_image_info="""
                """'{"title": "Murano Demo", "type": "cirros.demo"}'"""
            ),
        }

        # Individual attrs calculation and
        # merging with common attrs
        priority_mapping = {
            'controller': [600, 600, 500],
            'cinder': 700,
            'compute': 700
        }

        critical_mapping = {
            'primary-controller': True,
            'controller': False,
            'cinder': False,
            'compute': False
        }

        deployment_info = []
        for node in nodes_db:
            ips = assigned_ips[node.id]
            for role in sorted(node.roles):
                priority = priority_mapping[role]
                is_critical = critical_mapping[role]
                if isinstance(priority, list):
                    priority = priority.pop()

                individual_atts = {
                    'uid': str(node.id),
                    'status': node.status,
                    'role': role,
                    'online': node.online,
                    'fail_if_error': is_critical,
                    'fqdn': 'node-%d.%s' % (node.id, settings.DNS_DOMAIN),
                    'priority': priority,

                    'network_scheme': {
                        "version": "1.0",
                        "provider": "ovs",
                        "interfaces": {
                            "eth0": {
                                "L2": {"vlan_splinters": "off"},
                                "mtu": 1500
                            },
                            "eth1": {
                                "L2": {"vlan_splinters": "off"},
                                "mtu": 1500
                            },
                            "eth2": {
                                "L2": {"vlan_splinters": "off"},
                                "mtu": 1500
                            },
                        },
                        "endpoints": {
                            "br-mgmt": {"IP": [ips['management'] + "/24"]},
                            "br-ex": {
                                "IP": [ips['public'] + "/24"],
                                "gateway": "172.16.0.1"
                            },
                            "br-storage": {"IP": [ips['storage'] + "/24"]},
                            "br-fw-admin": {"IP": [ips['admin']]},
                        },
                        "roles": {
                            "management": "br-mgmt",
                            "mesh": "br-mgmt",
                            "ex": "br-ex",
                            "storage": "br-storage",
                            "fw-admin": "br-fw-admin",
                        },
                        "transformations": [
                            {
                                "action": "add-br",
                                "name": u"br-eth0"},
                            {
                                "action": "add-port",
                                "bridge": u"br-eth0",
                                "name": u"eth0"},
                            {
                                "action": "add-br",
                                "name": u"br-eth1"},
                            {
                                "action": "add-port",
                                "bridge": u"br-eth1",
                                "name": u"eth1"},
                            {
                                "action": "add-br",
                                "name": "br-ex"},
                            {
                                "action": "add-br",
                                "name": "br-mgmt"},
                            {
                                "action": "add-br",
                                "name": "br-storage"},
                            {
                                "action": "add-br",
                                "name": "br-fw-admin"},
                            {
                                "action": "add-patch",
                                "bridges": [u"br-eth0", "br-storage"],
                                "tags": [102, 0]},
                            {
                                "action": "add-patch",
                                "bridges": [u"br-eth0", "br-ex"],
                                "trunks": [0]},
                            {
                                "action": "add-patch",
                                "bridges": [u"br-eth0", "br-mgmt"],
                                "tags": [101, 0]},
                            {
                                "action": "add-patch",
                                "bridges": [u"br-eth1", "br-fw-admin"],
                                "trunks": [0]},
                        ]
                    }
                }

                individual_atts.update(common_attrs)
                individual_atts['glance']['image_cache_max_size'] = str(
                    manager.calc_glance_cache_size(node.attributes.volumes)
                )
                deployment_info.append(deepcopy(individual_atts))

        controller_nodes = filter(
            lambda node: node['role'] == 'controller',
            deployment_info)
        controller_nodes[0]['role'] = 'primary-controller'
        controller_nodes[0]['fail_if_error'] = True

        supertask = self.env.launch_deployment()
        deploy_task_uuid = [x.uuid for x in supertask.subtasks
                            if x.name == 'deployment'][0]

        deployment_msg = {
            'api_version': '1',
            'method': 'deploy',
            'respond_to': 'deploy_resp',
            'args': {}
        }

        deployment_msg['args']['task_uuid'] = deploy_task_uuid
        deployment_msg['args']['deployment_info'] = deployment_info

        provision_nodes = []
        admin_net = self.env.network_manager.get_admin_network_group()

        for n in sorted(self.env.nodes, key=lambda n: n.id):
            udev_interfaces_mapping = ','.join([
                '{0}_{1}'.format(i.mac, i.name) for i in n.interfaces])
            eth1_mac = [i.mac for i in n.interfaces if i.name == 'eth1'][0]

            pnd = {
                'profile': cluster_attrs['cobbler']['profile'],
                'power_type': 'ssh',
                'power_user': 'root',
                'kernel_options': {
                    'netcfg/choose_interface': eth1_mac,
                    'udevrules': udev_interfaces_mapping},
                'power_address': n.ip,
                'power_pass': settings.PATH_TO_BOOTSTRAP_SSH_KEY,
                'name': objects.Node.make_slave_name(n),
                'hostname': n.fqdn,
                'name_servers': '\"%s\"' % settings.DNS_SERVERS,
                'name_servers_search': '\"%s\"' % settings.DNS_SEARCH,
                'netboot_enabled': '1',
                'ks_meta': {
                    'fuel_version': cluster_db.fuel_version,
                    'puppet_auto_setup': 1,
                    'puppet_master': settings.PUPPET_MASTER_HOST,
                    'puppet_enable': 0,
                    'mco_auto_setup': 1,
                    'install_log_2_syslog': 1,
                    'mco_pskey': settings.MCO_PSKEY,
                    'mco_vhost': settings.MCO_VHOST,
                    'mco_host': settings.MCO_HOST,
                    'mco_user': settings.MCO_USER,
                    'mco_password': settings.MCO_PASSWORD,
                    'mco_connector': settings.MCO_CONNECTOR,
                    'mco_enable': 1,
                    'pm_data': {
                        'ks_spaces': n.attributes.volumes,
                        'kernel_params': objects.Node.get_kernel_params(n),
                    },
                    'auth_key': "\"%s\"" % cluster_attrs.get('auth_key', ''),
                    'mlnx_vf_num': "16",
                    'mlnx_plugin_mode': "disabled",
                    'mlnx_iser_enabled': False,
                }
            }
            orchestrator_data = objects.Release.get_orchestrator_data_dict(
                cluster_db.release)
            if orchestrator_data:
                pnd['ks_meta']['repo_metadata'] = \
                    orchestrator_data['repo_metadata']

            vlan_splinters = cluster_attrs.get('vlan_splinters', None)
            if vlan_splinters == 'kernel_lt':
                pnd['ks_meta']['kernel_lt'] = 1

            NetworkManager.assign_admin_ips(n.id, 1)

            admin_ip = self.env.network_manager.get_admin_ip_for_node(n)

            for i in n.meta.get('interfaces', []):
                if 'interfaces' not in pnd:
                    pnd['interfaces'] = {}
                pnd['interfaces'][i['name']] = {
                    'mac_address': i['mac'],
                    'static': '0',
                }
                if 'interfaces_extra' not in pnd:
                    pnd['interfaces_extra'] = {}
                pnd['interfaces_extra'][i['name']] = {
                    'peerdns': 'no',
                    'onboot': 'no'
                }

                if i['mac'] == n.mac:
                    pnd['interfaces'][i['name']]['dns_name'] = n.fqdn
                    pnd['interfaces_extra'][i['name']]['onboot'] = 'yes'
                    pnd['interfaces'][i['name']]['ip_address'] = admin_ip
                    pnd['interfaces'][i['name']]['netmask'] = str(
                        netaddr.IPNetwork(admin_net.cidr).netmask)

            provision_nodes.append(pnd)

        provision_task_uuid = filter(
            lambda t: t.name == 'provision',
            supertask.subtasks)[0].uuid

        provision_msg = {
            'api_version': '1',
            'method': 'provision',
            'respond_to': 'provision_resp',
            'args': {
                'task_uuid': provision_task_uuid,
                'provisioning_info': {
                    'engine': {
                        'url': settings.COBBLER_URL,
                        'username': settings.COBBLER_USER,
                        'password': settings.COBBLER_PASSWORD,
                        'master_ip': settings.MASTER_IP},
                    'nodes': provision_nodes}}}

        args, kwargs = nailgun.task.manager.rpc.cast.call_args
        self.assertEqual(len(args), 2)
        self.assertEqual(len(args[1]), 2)

        self.datadiff(args[1][0], provision_msg)
        self.datadiff(args[1][1], deployment_msg)

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_deploy_and_remove_correct_nodes_and_statuses(self, mocked_rpc):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {
                    "pending_addition": True,
                },
                {
                    "status": "error",
                    "pending_deletion": True
                }
            ]
        )
        self.env.launch_deployment()

        # launch_deployment kicks ClusterChangesHandler
        # which in turns launches DeploymentTaskManager
        # which runs DeletionTask, ProvisionTask and DeploymentTask.
        # DeletionTask is sent to one orchestrator worker and
        # ProvisionTask and DeploymentTask messages are sent to
        # another orchestrator worker.
        # That is why we expect here list of two sets of
        # arguments in mocked nailgun.rpc.cast
        # The first set of args is for deletion task and
        # the second one is for provisioning and deployment.

        # remove_nodes method call [0][0][1]
        n_rpc_remove = nailgun.task.task.rpc.cast. \
            call_args_list[0][0][1]['args']['nodes']
        self.assertEqual(len(n_rpc_remove), 1)
        self.assertEqual(n_rpc_remove[0]['uid'], self.env.nodes[1].id)

        # provision method call [1][0][1][0]
        n_rpc_provision = nailgun.task.manager.rpc.cast. \
            call_args_list[1][0][1][0]['args']['provisioning_info']['nodes']
        # Nodes will be appended in provision list if
        # they 'pending_deletion' = False and
        # 'status' in ('discover', 'provisioning') or
        # 'status' = 'error' and 'error_type' = 'provision'
        # So, only one node from our list will be appended to
        # provision list.
        self.assertEqual(len(n_rpc_provision), 1)
        self.assertEqual(
            n_rpc_provision[0]['name'],
            objects.Node.make_slave_name(self.env.nodes[0])
        )

        # deploy method call [1][0][1][1]
        n_rpc_deploy = nailgun.task.manager.rpc.cast.call_args_list[
            1][0][1][1]['args']['deployment_info']
        self.assertEqual(len(n_rpc_deploy), 1)
        self.assertEqual(n_rpc_deploy[0]['uid'], str(self.env.nodes[0].id))

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_deploy_multinode_neutron_gre_w_custom_public_ranges(self,
                                                                 mocked_rpc):
        self.env.create(
            cluster_kwargs={'net_provider': 'neutron',
                            'net_segment_type': 'gre'},
            nodes_kwargs=[{"pending_addition": True},
                          {"pending_addition": True},
                          {"pending_addition": True},
                          {"pending_addition": True},
                          {"pending_addition": True}]
        )

        net_data = jsonutils.loads(
            self.env.neutron_networks_get(self.env.clusters[0].id).body)
        pub = filter(lambda ng: ng['name'] == 'public',
                     net_data['networks'])[0]
        pub.update({'ip_ranges': [['172.16.0.10', '172.16.0.13'],
                                  ['172.16.0.20', '172.16.0.22']]})

        resp = self.env.neutron_networks_put(self.env.clusters[0].id, net_data)
        self.assertEqual(resp.status_code, 202)
        task = jsonutils.loads(resp.body)
        self.assertEqual(task['status'], 'ready')

        self.env.launch_deployment()

        args, kwargs = nailgun.task.manager.rpc.cast.call_args
        self.assertEqual(len(args), 2)
        self.assertEqual(len(args[1]), 2)

        n_rpc_deploy = args[1][1]['args']['deployment_info']
        self.assertEqual(len(n_rpc_deploy), 5)
        pub_ips = ['172.16.0.11', '172.16.0.12', '172.16.0.13',
                   '172.16.0.20', '172.16.0.21']
        for n in n_rpc_deploy:
            for i, n_common_args in enumerate(n['nodes']):
                self.assertEqual(n_common_args['public_address'], pub_ips[i])

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_deploy_ha_neutron_gre_w_custom_public_ranges(self, mocked_rpc):
        self.env.create(
            cluster_kwargs={'mode': 'ha_compact',
                            'net_provider': 'neutron',
                            'net_segment_type': 'gre'},
            nodes_kwargs=[{"pending_addition": True},
                          {"pending_addition": True},
                          {"pending_addition": True},
                          {"pending_addition": True},
                          {"pending_addition": True}]
        )

        net_data = jsonutils.loads(
            self.env.neutron_networks_get(self.env.clusters[0].id).body)
        pub = filter(lambda ng: ng['name'] == 'public',
                     net_data['networks'])[0]
        pub.update({'ip_ranges': [['172.16.0.10', '172.16.0.12'],
                                  ['172.16.0.20', '172.16.0.22']]})

        resp = self.env.neutron_networks_put(self.env.clusters[0].id, net_data)
        self.assertEqual(resp.status_code, 202)
        task = jsonutils.loads(resp.body)
        self.assertEqual(task['status'], 'ready')

        self.env.launch_deployment()

        args, kwargs = nailgun.task.manager.rpc.cast.call_args
        self.assertEqual(len(args), 2)
        self.assertEqual(len(args[1]), 2)

        n_rpc_deploy = args[1][1]['args']['deployment_info']
        self.assertEqual(len(n_rpc_deploy), 5)
        pub_ips = ['172.16.0.11', '172.16.0.12',
                   '172.16.0.20', '172.16.0.21', '172.16.0.22']
        for n in n_rpc_deploy:
            self.assertEqual(n['public_vip'], '172.16.0.10')
            for i, n_common_args in enumerate(n['nodes']):
                self.assertEqual(n_common_args['public_address'], pub_ips[i])

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_deploy_neutron_gre_w_changed_public_cidr(self, mocked_rpc):
        self.env.create(
            cluster_kwargs={'net_provider': 'neutron',
                            'net_segment_type': 'gre'},
            nodes_kwargs=[{"pending_addition": True},
                          {"pending_addition": True}]
        )

        net_data = jsonutils.loads(
            self.env.neutron_networks_get(self.env.clusters[0].id).body)
        pub = filter(lambda ng: ng['name'] == 'public',
                     net_data['networks'])[0]
        pub.update({'ip_ranges': [['172.16.10.10', '172.16.10.122']],
                    'cidr': '172.16.10.0/24',
                    'gateway': '172.16.10.1'})
        net_data['networking_parameters']['floating_ranges'] = \
            [['172.16.10.130', '172.16.10.254']]

        resp = self.env.neutron_networks_put(self.env.clusters[0].id, net_data)
        self.assertEqual(resp.status_code, 202)
        task = jsonutils.loads(resp.body)
        self.assertEqual(task['status'], 'ready')

        self.env.launch_deployment()

        args, kwargs = nailgun.task.manager.rpc.cast.call_args
        self.assertEqual(len(args), 2)
        self.assertEqual(len(args[1]), 2)

        n_rpc_deploy = args[1][1]['args']['deployment_info']
        self.assertEqual(len(n_rpc_deploy), 2)
        pub_ips = ['172.16.10.11', '172.16.10.12']
        for n in n_rpc_deploy:
            for i, n_common_args in enumerate(n['nodes']):
                self.assertEqual(n_common_args['public_address'], pub_ips[i])

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_deploy_neutron_error_not_enough_ip_addresses(self, mocked_rpc):
        self.env.create(
            cluster_kwargs={'net_provider': 'neutron',
                            'net_segment_type': 'gre'},
            nodes_kwargs=[{"pending_addition": True},
                          {"pending_addition": True},
                          {"pending_addition": True}]
        )

        net_data = jsonutils.loads(
            self.env.neutron_networks_get(self.env.clusters[0].id).body)
        pub = filter(lambda ng: ng['name'] == 'public',
                     net_data['networks'])[0]
        pub.update({'ip_ranges': [['172.16.0.10', '172.16.0.11']]})

        resp = self.env.neutron_networks_put(self.env.clusters[0].id, net_data)
        self.assertEqual(resp.status_code, 202)
        task = jsonutils.loads(resp.body)
        self.assertEqual(task['status'], 'ready')

        task = self.env.launch_deployment()

        self.assertEqual(task.status, 'error')
        self.assertEqual(
            task.message,
            'Not enough IP addresses. Public network must have at least '
            '3 IP addresses for the current environment.')

    def test_occurs_error_not_enough_ip_addresses(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {'pending_addition': True},
                {'pending_addition': True},
                {'pending_addition': True}])

        cluster = self.env.clusters[0]

        public_network = self.db.query(
            NetworkGroup).filter_by(name='public').first()

        net_data = {
            "networks": [{
                'id': public_network.id,
                'cidr': '220.0.1.0/24',
                'gateway': '220.0.1.1',
                'ip_ranges': [[
                    '220.0.1.2',
                    '220.0.1.3']]}]}

        self.app.put(
            reverse(
                'NovaNetworkConfigurationHandler',
                kwargs={'cluster_id': cluster.id}),
            jsonutils.dumps(net_data),
            headers=self.default_headers,
            expect_errors=True)

        task = self.env.launch_deployment()

        self.assertEqual(task.status, 'error')
        self.assertEqual(
            task.message,
            'Not enough IP addresses. Public network must have at least '
            '3 IP addresses for the current environment.')

    def test_occurs_error_not_enough_free_space(self):
        meta = self.env.default_metadata()
        meta['disks'] = [{
            "model": "TOSHIBA MK1002TS",
            "name": "sda",
            "disk": "sda",
            # 8GB
            "size": 8000000}]

        self.env.create(
            nodes_kwargs=[
                {"meta": meta, "pending_addition": True}
            ]
        )
        node_db = self.env.nodes[0]

        task = self.env.launch_deployment()

        self.assertEqual(task.status, 'error')
        self.assertEqual(
            task.message,
            "Node '%s' has insufficient disk space" %
            node_db.human_readable_name)

    # TODO(awoodward): Purge multinode
    def test_occurs_error_not_enough_controllers_for_multinode(self):
        self.env.create(
            cluster_kwargs={
                'mode': 'multinode'
            },
            nodes_kwargs=[
                {'roles': ['compute'], 'pending_addition': True}])

        task = self.env.launch_deployment()

        self.assertEqual(task.status, 'error')
        self.assertEqual(
            task.message,
            "Not enough controllers, multinode mode requires at least 1 "
            "controller")

    def test_occurs_error_not_enough_controllers_for_ha(self):
        self.env.create(
            nodes_kwargs=[
                {'roles': ['compute'], 'pending_addition': True}])

        task = self.env.launch_deployment()

        self.assertEqual(task.status, 'error')
        self.assertEqual(
            task.message,
            'Not enough controllers, ha_compact '
            'mode requires at least 1 controller')

    def test_occurs_error_not_enough_osds_for_ceph(self):
        cluster = self.env.create(
            nodes_kwargs=[
                {'roles': ['controller', 'ceph-osd'],
                 'pending_addition': True}])

        self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster['id']}),
            params=jsonutils.dumps({
                'editable': {
                    'storage': {'volumes_ceph': {'value': True},
                                'osd_pool_size': {'value': 3}}}}),
            headers=self.default_headers)

        task = self.env.launch_deployment()

        self.assertEqual(task.status, 'error')
        self.assertEqual(
            task.message,
            'Number of OSD nodes (1) cannot be less than '
            'the Ceph object replication factor (3). '
            'Please either assign ceph-osd role to more nodes, '
            'or reduce Ceph replication factor in the Settings tab.')

    @fake_tasks(godmode=True)
    def test_enough_osds_for_ceph(self):
        cluster = self.env.create(
            nodes_kwargs=[
                {'roles': ['controller', 'ceph-osd'],
                 'pending_addition': True}])
        self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster['id']}),
            params=jsonutils.dumps({
                'editable': {
                    'storage': {'volumes_ceph': {'value': True},
                                'osd_pool_size': {'value': 1}}}}),
            headers=self.default_headers)

        task = self.env.launch_deployment()
        self.assertIn(task.status, ('running', 'ready'))

    @fake_tasks()
    def test_admin_untagged_intersection(self):
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta, [{
            "mac": "00:00:00:00:00:66",
            "max_speed": 1000,
            "name": "eth0",
            "current_speed": 1000
        }, {
            "mac": "00:00:00:00:00:77",
            "max_speed": 1000,
            "name": "eth1",
            "current_speed": None}])

        self.env.create(
            nodes_kwargs=[
                {
                    'api': True,
                    'roles': ['controller'],
                    'pending_addition': True,
                    'meta': meta,
                    'mac': "00:00:00:00:00:66"
                }
            ]
        )
        cluster_id = self.env.clusters[0].id

        resp = self.env.nova_networks_get(cluster_id)
        nets = jsonutils.loads(resp.body)
        for net in nets["networks"]:
            if net["name"] in ["management", ]:
                net["vlan_start"] = None
        self.env.nova_networks_put(cluster_id, nets)

        supertask = self.env.launch_deployment()
        self.env.wait_error(supertask)

    def test_empty_cluster_deploy_error(self):
        self.env.create(nodes_kwargs=[])
        resp = self.app.put(
            reverse(
                'ClusterChangesHandler',
                kwargs={'cluster_id': self.env.clusters[0].id}
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)

    def datadiff(self, node1, node2, path=None):
        if path is None:
            path = []

        # print("Path: {0}".format("->".join(path)))
        if not isinstance(node1, dict) or not isinstance(node2, dict):
            if isinstance(node1, list):
                newpath = path[:]
                for i, keys in enumerate(izip(node1, node2)):
                    newpath.append(str(i))
                    self.datadiff(keys[0], keys[1], newpath)
                    newpath.pop()
            elif node1 != node2:
                err = "Values differ: {0} != {1}".format(
                    str(node1),
                    str(node2)
                )
                raise Exception(err)
        else:
            newpath = path[:]
            for key1, key2 in zip(
                sorted(node1.keys()),
                sorted(node2.keys())
            ):
                if key1 != key2:
                    err = "Keys differ: {0} != {1}".format(
                        str(key1),
                        str(key2)
                    )
                    raise Exception(err)
                newpath.append(key1)
                self.datadiff(node1[key1], node2[key2], newpath)
                newpath.pop()
