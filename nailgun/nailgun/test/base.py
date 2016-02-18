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

try:
    from unittest.case import TestCase
except ImportError:
    # Runing unit-tests in production environment
    from unittest2.case import TestCase

import copy
import mock
import os
import re
import six
from six.moves import range
import time
import uuid

from datetime import datetime
from functools import partial
from itertools import izip
from netaddr import IPNetwork
from random import randint

from oslo_serialization import jsonutils

import sqlalchemy as sa
import web
from webtest import app

import nailgun

from nailgun import consts
from nailgun.errors import errors
from nailgun.settings import settings

from nailgun.db import db
from nailgun.db import flush
from nailgun.db import syncdb

from nailgun.logger import logger

from nailgun.db.sqlalchemy.fixman import load_fake_deployment_tasks
from nailgun.db.sqlalchemy.fixman import load_fixture
from nailgun.db.sqlalchemy.fixman import upload_fixture
from nailgun.db.sqlalchemy.models import ClusterPluginLink
from nailgun.db.sqlalchemy.models import IPAddr
from nailgun.db.sqlalchemy.models import NodeNICInterface
from nailgun.db.sqlalchemy.models import Notification
from nailgun.db.sqlalchemy.models import PluginLink
from nailgun.db.sqlalchemy.models import Task


# here come objects
from nailgun.objects import Cluster
from nailgun.objects import ClusterPlugins
from nailgun.objects import MasterNodeSettings
from nailgun.objects import NetworkGroup
from nailgun.objects import Node
from nailgun.objects import NodeGroup
from nailgun.objects import OpenstackConfig
from nailgun.objects import Plugin
from nailgun.objects import Release

from nailgun.app import build_app
from nailgun.consts import NETWORK_INTERFACE_TYPES
from nailgun.middleware.connection_monitor import ConnectionMonitorMiddleware
from nailgun.middleware.keystone import NailgunFakeKeystoneAuthMiddleware
from nailgun.network.manager import NetworkManager
from nailgun.network.template import NetworkTemplate
from nailgun.utils import dict_merge
from nailgun.utils import reverse


class TimeoutError(Exception):
    pass


def test_db_driver(handler):
    try:
        return handler()
    except web.HTTPError:
        if str(web.ctx.status).startswith(("4", "5")):
            db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.commit()
        # we do not remove session in tests


class EnvironmentManager(object):
    _regex_type = type(re.compile("regex"))

    def __init__(self, app, session=None):
        self.db = session or db()
        self.app = app
        self.tester = TestCase
        self.tester.runTest = lambda a: None
        self.tester = self.tester()
        self.here = os.path.abspath(os.path.dirname(__file__))
        self.fixture_dir = os.path.join(self.here, "..", "fixtures")
        self.default_headers = {
            "Content-Type": "application/json"
        }
        self.releases = []
        self.clusters = []
        self.nodes = []
        self.plugins = []
        self.openstack_configs = []
        self.network_manager = NetworkManager

    def create(self, **kwargs):
        release_data = kwargs.pop('release_kwargs', {"api": False})
        cluster_data = kwargs.pop('cluster_kwargs', {})
        if 'release_id' not in cluster_data:
            cluster_data['release_id'] = self.create_release(**release_data).id
        cluster = self.create_cluster(
            **cluster_data
        )
        for node_kwargs in kwargs.pop('nodes_kwargs', []):
            if "cluster_id" not in node_kwargs:
                if isinstance(cluster, dict):
                    node_kwargs["cluster_id"] = cluster["id"]
                else:
                    node_kwargs["cluster_id"] = cluster.id
            node_kwargs.setdefault("api", False)
            if "pending_roles" not in node_kwargs:
                node_kwargs.setdefault("roles", ["controller"])
            self.create_node(
                **node_kwargs
            )
        return cluster

    def create_release(self, api=False, **kwargs):
        os = kwargs.get(
            'operating_system', consts.RELEASE_OS.centos)
        version = kwargs.get(
            'version', '{0}-6.1'.format(randint(0, 100000000)))

        # NOTE(ikalnitsky): In order to do not read each time openstack.yaml
        # we're reading it once and then look for needed release.
        releases = self.read_fixtures(('openstack',))
        release_data = next((
            r for r in releases if r['fields']['operating_system'] == os),
            releases[0])
        release_data = release_data['fields']

        release_data.update({
            'name': u"release_name_" + version,
            'version': version,
            'state': consts.RELEASE_STATES.available,
            'description': u"release_desc" + version,
        })

        if kwargs.get('deployment_tasks') is None:
            kwargs['deployment_tasks'] = \
                load_fake_deployment_tasks(apply_to_db=False)

        release_data.update(kwargs)
        if api:
            resp = self.app.post(
                reverse('ReleaseCollectionHandler'),
                params=jsonutils.dumps(release_data),
                headers=self.default_headers
            )
            self.tester.assertEqual(resp.status_code, 201)
            release = resp.json_body
            self.releases.append(
                self.db.query(Release).get(release['id'])
            )
        else:
            release = Release.create(release_data)
            db().commit()
            self.releases.append(release)
        return release

    def get_role(self, release_id, role_name, expect_errors=False):
        return self.app.get(
            reverse(
                'RoleHandler',
                {'role_name': role_name, 'release_id': release_id}),
            headers=self.default_headers,
            expect_errors=expect_errors
        )

    def create_openstack_config(self, api=False, **kwargs):
        if api:
            resp = self.app.post(
                reverse('OpenstackConfigCollectionHandler'),
                params=jsonutils.dumps(kwargs),
                headers=self.default_headers
            )
            self.tester.assertEqual(resp.status_code, 201)
            config = resp.json_body
            self.openstack_configs.append(
                self.db.query(OpenstackConfig).get(config['id']))
        else:
            config = OpenstackConfig.create(kwargs)
            db().flush()
            self.openstack_configs.append(config)
        return config

    def update_role(self, release_id, role_name, data, expect_errors=False):
        return self.app.put(
            reverse(
                'RoleHandler',
                {'role_name': role_name, 'release_id': release_id}),
            jsonutils.dumps(data),
            headers=self.default_headers,
            expect_errors=expect_errors
        )

    def delete_role(self, release_id, role_name, expect_errors=False):
        return self.app.delete(
            reverse(
                'RoleHandler',
                {'role_name': role_name, 'release_id': release_id}),
            headers=self.default_headers,
            expect_errors=expect_errors
        )

    def create_role(self, release_id, data, expect_errors=False):
        return self.app.post(
            reverse('RoleCollectionHandler', {'release_id': release_id}),
            jsonutils.dumps(data),
            headers=self.default_headers,
            expect_errors=expect_errors
        )

    def create_cluster(self, api=True, exclude=None, **kwargs):
        cluster_data = {
            'name': 'cluster-api-' + str(randint(0, 1000000)),
        }
        editable_attributes = kwargs.pop('editable_attributes', None)
        vmware_attributes = kwargs.pop('vmware_attributes', None)

        if kwargs:
            cluster_data.update(kwargs)

        if 'release_id' not in cluster_data:
            cluster_data['release_id'] = self.create_release(api=False).id

        if exclude and isinstance(exclude, list):
            for ex in exclude:
                try:
                    del cluster_data[ex]
                except KeyError as err:
                    logger.warning(err)
        if api:
            resp = self.app.post(
                reverse('ClusterCollectionHandler'),
                jsonutils.dumps(cluster_data),
                headers=self.default_headers,
                expect_errors=True
            )
            self.tester.assertEqual(resp.status_code, 201, resp.body)
            cluster = resp.json_body
            cluster_db = Cluster.get_by_uid(cluster['id'])
        else:
            cluster = Cluster.create(cluster_data)
            cluster_db = cluster
            db().commit()
        self.clusters.append(cluster_db)

        if editable_attributes:
            Cluster.patch_attributes(cluster_db,
                                     {'editable': editable_attributes})
        if vmware_attributes:
            Cluster.update_vmware_attributes(cluster_db, vmware_attributes)
        return cluster

    def create_node(
            self, api=False,
            exclude=None, expect_http=201,
            expected_error=None,
            **kwargs):
        # TODO(alekseyk) Simplify 'interfaces' and 'mac' manipulation logic
        metadata = kwargs.get('meta', {})
        default_metadata = self.default_metadata()
        default_metadata.update(metadata)

        mac = kwargs.get('mac', self.generate_random_mac())
        if default_metadata['interfaces']:
            if not metadata or 'interfaces' not in metadata:
                default_metadata['interfaces'][0]['mac'] = mac
                default_metadata['interfaces'][0]['pxe'] = True
                for iface in default_metadata['interfaces'][1:]:
                    if 'mac' in iface:
                        iface['mac'] = self.generate_random_mac()
            else:
                for iface in default_metadata['interfaces']:
                    if iface.get('pxe'):
                        if not iface.get('mac'):
                            iface['mac'] = mac
                        elif 'mac' not in kwargs:
                            mac = iface['mac']
                    if iface.get('mac') == mac:
                        break
                else:
                    default_metadata['interfaces'][0]['mac'] = mac
                    default_metadata['interfaces'][0]['pxe'] = True

        node_data = {
            'mac': mac,
            'status': 'discover',
            'ip': '10.20.0.130',
            'meta': default_metadata
        }
        if kwargs:
            meta = kwargs.pop('meta', None)
            node_data.update(kwargs)
            if meta:
                kwargs['meta'] = meta

        if exclude and isinstance(exclude, list):
            for ex in exclude:
                try:
                    del node_data[ex]
                except KeyError as err:
                    logger.warning(err)
        if api:
            resp = self.app.post(
                reverse('NodeCollectionHandler'),
                jsonutils.dumps(node_data),
                headers=self.default_headers,
                expect_errors=True
            )
            self.tester.assertEqual(resp.status_code, expect_http, resp.body)
            if expected_error:
                self.tester.assertEqual(
                    resp.json_body["message"],
                    expected_error
                )
            if str(expect_http)[0] != "2":
                return None
            self.tester.assertEqual(resp.status_code, expect_http)
            node = resp.json_body
            node_db = Node.get_by_uid(node['id'])
            if 'interfaces' not in node_data['meta'] \
                    or not node_data['meta']['interfaces']:
                self._set_interfaces_if_not_set_in_meta(
                    node_db.id,
                    kwargs.get('meta', None))
            self.nodes.append(node_db)
        else:
            node = Node.create(node_data)
            db().commit()
            self.nodes.append(node)

        return node

    def create_nodes(self, count, *args, **kwargs):
        """Helper to generate specific number of nodes."""
        return [self.create_node(*args, **kwargs) for _ in range(count)]

    def create_nodes_w_interfaces_count(self,
                                        nodes_count, if_count=2, **kwargs):
        """Create nodes_count nodes with if_count interfaces each

        Default random MAC is generated for each interface
        """
        nodes = []
        for i in range(nodes_count):
            meta = self.default_metadata()
            if_list = [
                {
                    "name": "eth{0}".format(i),
                    "mac": self.generate_random_mac(),
                }
                for i in range(if_count)]
            if_list[0]['pxe'] = True
            self.set_interfaces_in_meta(meta, if_list)
            nodes.append(self.create_node(meta=meta, mac=if_list[0]['mac'],
                                          **kwargs))
        return nodes

    def create_task(self, **kwargs):
        task = Task(**kwargs)
        self.db.add(task)
        self.db.commit()
        return task

    def create_notification(self, **kwargs):
        notif_data = {
            "topic": "discover",
            "message": "Test message",
            "status": "unread",
            "datetime": datetime.now()
        }
        if kwargs:
            notif_data.update(kwargs)
        notification = Notification()
        notification.cluster_id = notif_data.get("cluster_id")
        for f, v in notif_data.iteritems():
            setattr(notification, f, v)
        self.db.add(notification)
        self.db.commit()
        return notification

    def create_node_group(self, api=True, expect_errors=False,
                          cluster_id=None, **kwargs):
        cluster_id = self._get_cluster_by_id(cluster_id).id
        ng_data = {
            'cluster_id': cluster_id,
            'name': 'test_ng'
        }
        if kwargs:
            ng_data.update(kwargs)
        if api:
            resp = self.app.post(
                reverse('NodeGroupCollectionHandler'),
                jsonutils.dumps(ng_data),
                headers=self.default_headers,
                expect_errors=expect_errors
            )

            ng = resp
        else:
            ng = NodeGroup.create(ng_data)
            db().flush()

        return ng

    def create_ip_addrs_by_rules(self, cluster, rules):
        """Manually create VIPs in database basing on given rules

        Format exmaple for rules
        {
            'management': {
                'haproxy': '192.168.0.1',
                'vrouter': '192.168.0.2',
            }
        }

        :param cluster: cluster ORM instance
        :param rules: mapping of networks and VIPs information needed
            for proper database entry creation
        """
        created_ips = []
        for net_group in cluster.network_groups:
            if net_group.name not in rules:
                continue
            vips_by_names = rules[net_group.name]
            for vip_name, ip_addr in six.iteritems(vips_by_names):
                ip = IPAddr(
                    network=net_group.id,
                    ip_addr=ip_addr,
                    vip_name=vip_name,
                )
                self.db.add(ip)
                created_ips.append(ip)
        if created_ips:
            self.db.flush()
        return created_ips

    def disable_task_deploy(self, cluster):
        cluster.attributes.editable['common']['task_deploy']['value'] = False
        cluster.attributes.editable.changed()
        self.db().flush()

    def delete_node_group(self, ng_id, status_code=200, api=True):
        if api:
            return self.app.delete(
                reverse(
                    'NodeGroupHandler',
                    kwargs={'obj_id': ng_id}
                ),
                headers=self.default_headers,
                expect_errors=(status_code != 200)
            )
        else:
            ng = db().query(NodeGroup).get(ng_id)
            db().delete(ng)
            db().flush()

    def setup_networks_for_nodegroup(
            self, cluster_id, node_group, cidr_start, floating_ranges=None):
        """Setup networks of particular node group in multi-node-group mode.

        :param cluster_id: Cluster Id
        :param node_group: NodeGroup instance
        :param cidr_start: first two octets of CIDR which are common for all
            networks (e.g. "192.168")
        :param floating_ranges: Floating IP ranges
        :return: response from network setup API request
        """
        ng2_networks = {
            'fuelweb_admin': {'cidr': '{0}.9.0/24'.format(cidr_start),
                              'ip_ranges': [['{0}.9.2'.format(cidr_start),
                                             '{0}.9.254'.format(cidr_start)]],
                              'gateway': '{0}.9.1'.format(cidr_start)},
            'public': {'cidr': '{0}.0.0/24'.format(cidr_start),
                       'ip_ranges': [['{0}.0.2'.format(cidr_start),
                                      '{0}.0.127'.format(cidr_start)]],
                       'gateway': '{0}.0.1'.format(cidr_start)},
            'management': {'cidr': '{0}.1.0/24'.format(cidr_start),
                           'gateway': '{0}.1.1'.format(cidr_start)},
            'storage': {'cidr': '{0}.2.0/24'.format(cidr_start),
                        'gateway': '{0}.2.1'.format(cidr_start)},
            'private': {'cidr': '{0}.3.0/24'.format(cidr_start),
                        'gateway': '{0}.3.1'.format(cidr_start)},
        }
        netw_ids = set(net.id for net in node_group.networks)
        netconfig = self.neutron_networks_get(cluster_id).json_body
        for net in netconfig['networks']:
            if not net['meta']['notation']:
                continue
            if net['id'] in netw_ids and net['name'] in ng2_networks:
                for pkey, pval in six.iteritems(ng2_networks[net['name']]):
                    net[pkey] = pval
            net['meta']['use_gateway'] = True
        if floating_ranges:
            netconfig['networking_parameters']['floating_ranges'] = \
                floating_ranges
        resp = self.neutron_networks_put(cluster_id, netconfig)
        return resp

    def create_plugin(self, api=False, cluster=None, enabled=True, **kwargs):
        plugin_data = self.get_default_plugin_metadata(**kwargs)

        if api:
            resp = self.app.post(
                reverse('PluginCollectionHandler'),
                jsonutils.dumps(plugin_data),
                headers=self.default_headers,
                expect_errors=False
            )
            plugin = Plugin.get_by_uid(resp.json_body['id'])
        else:
            plugin = Plugin.create(plugin_data)

        self.plugins.append(plugin)

        # Enable plugin for specific cluster
        if cluster:
            cluster.plugins.append(plugin)
            ClusterPlugins.set_attributes(
                cluster.id, plugin.id, enabled=enabled,
                attrs=plugin.attributes_metadata or {}
            )
        return plugin

    def create_cluster_plugin_link(self, **kwargs):
        dash_data = {
            "title": "title",
            "url": "url",
            "description": "description",
            "cluster_id": None,
            "hidden": False
        }
        if kwargs:
            dash_data.update(kwargs)
        cluster_plugin_link = ClusterPluginLink()
        cluster_plugin_link.update(dash_data)
        self.db.add(cluster_plugin_link)
        self.db.commit()
        return cluster_plugin_link

    def create_plugin_link(self, **kwargs):
        dash_data = {
            "title": "title",
            "url": "url",
            "description": "description",
            "plugin_id": None,
            "hidden": False
        }
        if kwargs:
            dash_data.update(kwargs)
        plugin_link = PluginLink()
        plugin_link.update(dash_data)
        self.db.add(plugin_link)
        self.db.commit()
        return plugin_link

    def default_metadata(self):
        item = self.find_item_by_pk_model(
            self.read_fixtures(("sample_environment",)),
            1, 'nailgun.node')
        return item.get('fields').get('meta', {})

    def generate_random_mac(self):
        mac = [randint(0x00, 0x7f) for _ in range(6)]
        return ':'.join(map(lambda x: "%02x" % x, mac)).lower()

    def generate_interfaces_in_meta(self, amount):
        nics = []
        for i in range(amount):
            nics.append(
                {
                    'name': 'eth{0}'.format(i),
                    'mac': self.generate_random_mac(),
                    'current_speed': 100,
                    'max_speed': 1000,
                    'offloading_modes': [
                        {
                            'name': 'enabled_offloading_mode',
                            'state': True,
                            "sub": [
                                {
                                    'name': 'disabled_offloading_sub_mode',
                                    'state': False,
                                    "sub": []
                                }
                            ]
                        },
                        {
                            'name': 'disabled_offloading_mode',
                            'state': False,
                            "sub": []
                        }
                    ]
                }
            )
        self.set_admin_ip_for_for_single_interface(nics)
        return {'interfaces': nics}

    def _set_interfaces_if_not_set_in_meta(self, node_id, meta):
        if not meta or 'interfaces' not in meta:
            self._add_interfaces_to_node(node_id)

    def _create_interfaces_from_meta(self, node):
        # Create interfaces from meta
        for interface in node.meta['interfaces']:
            interface = NodeNICInterface(
                mac=interface.get('mac'),
                name=interface.get('name'),
                ip_addr=interface.get('ip'),
                netmask=interface.get('netmask')
            )
            self.db.add(interface)
            node.nic_interfaces.append(interface)

        self.db.flush()
        # If node in a cluster then assign networks for all interfaces
        if node.cluster_id:
            self.network_manager.assign_networks_by_default(node)
        # At least one interface should have
        # same ip as mac in meta
        if node.nic_interfaces and not \
           filter(lambda i: node.mac == i.mac, node.nic_interfaces):

            node.nic_interfaces[0].mac = node.mac
        self.db.commit()

    def _add_interfaces_to_node(self, node_id, count=1):
        interfaces = []
        node = self.db.query(Node.model).get(node_id)
        networks_to_assign = \
            list(node.cluster.network_groups) if node.cluster else []

        for i in range(count):
            interface = NodeNICInterface(
                node_id=node_id,
                name='eth{0}'.format(i),
                mac=self.generate_random_mac(),
                current_speed=100,
                max_speed=1000,
                assigned_networks=networks_to_assign
            )
            self.db.add(interface)
            self.db.commit()

            interfaces.append(interface)
            # assign all networks to first NIC
            networks_to_assign = []

        return interfaces

    def set_admin_ip_for_for_single_interface(self, interfaces):
        """Set admin ip for single interface if it not setted yet."""
        ips = [interface.get('ip') for interface in interfaces]
        admin_ips = [
            ip for ip in ips
            if self.network_manager.is_ip_belongs_to_admin_subnet(ip)]

        if not admin_ips:
            admin_cidr = NetworkGroup.get_admin_network_group().cidr
            interfaces[0]['ip'] = str(IPNetwork(admin_cidr).ip)

    def set_interfaces_in_meta(self, meta, interfaces):
        """Set interfaces in metadata."""
        meta['interfaces'] = interfaces
        self.set_admin_ip_for_for_single_interface(meta['interfaces'])
        return meta['interfaces']

    def get_default_roles(self):
        return list(self.get_default_roles_metadata.keys())

    def get_default_volumes_metadata(self):
        return self.read_fixtures(
            ('openstack',))[0]['fields']['volumes_metadata']

    def get_default_roles_metadata(self):
        return self.read_fixtures(
            ('openstack',))[0]['fields']['roles_metadata']

    def get_default_networks_metadata(self):
        return self.read_fixtures(
            ('openstack',))[0]['fields']['networks_metadata']

    def get_default_attributes_metadata(self):
        return self.read_fixtures(
            ['openstack'])[0]['fields']['attributes_metadata']

    def get_default_plugin_env_config(self, **kwargs):
        return {
            'attributes': {
                '{0}_text'.format(kwargs.get('plugin_name', 'plugin_name')): {
                    'value': kwargs.get('value', 'value'),
                    'type': kwargs.get('type', 'text'),
                    'description': kwargs.get('description', 'description'),
                    'weight': kwargs.get('weight', 25),
                    'label': kwargs.get('label', 'label')}}}

    def get_default_plugin_node_roles_config(self, **kwargs):
        node_roles = {
            'testing_plugin': {
                'name': 'Some plugin role',
                'description': 'Some description'
            }
        }

        node_roles.update(kwargs)
        return node_roles

    def get_default_plugin_volumes_config(self, **kwargs):
        volumes = {
            'volumes_roles_mapping': {
                'testing_plugin': [
                    {'allocate_size': 'min', 'id': 'os'},
                    {'allocate_size': 'all', 'id': 'test_volume'}
                ]
            },
            'volumes': [
                {'id': 'test_volume', 'type': 'vg'}
            ]
        }

        volumes.update(kwargs)
        return volumes

    def get_default_network_roles_config(self, **kwargs):
        network_roles = [
            {
                'id': 'test_network_role',
                'default_mapping': 'public',
                'properties': {
                    'subnet': 'true',
                    'gateway': 'false',
                    'vip': [
                        {'name': 'test_vip_1', 'shared': False},
                        {'name': 'test_vip_2', 'shared': False}
                    ]
                }
            }
        ]

        network_roles[0].update(kwargs)
        return network_roles

    def get_default_plugin_deployment_tasks(self, **kwargs):
        deployment_tasks = [
            {
                'id': 'role-name',
                'type': 'group',
                'role': ['role-name'],
                'requires': ['controller'],
                'required_for': ['deploy_end'],
                'parameters': {
                    'strategy': {
                        'type': 'parallel'
                    }
                }
            }
        ]

        deployment_tasks[0].update(kwargs)
        return deployment_tasks

    def get_default_plugin_tasks(self, **kwargs):
        default_tasks = [
            {
                'role': '[test_role]',
                'stage': 'post_deployment',
                'type': 'puppet',
                'parameters': {
                    'puppet_manifest': '/etc/puppet/modules/test_manigest.pp',
                    'puppet_modules': '/etc/puppet/modules',
                    'timeout': 720
                }
            }
        ]

        default_tasks[0].update(kwargs)
        return default_tasks

    def get_default_plugin_metadata(self, **kwargs):
        sample_plugin = {
            'version': '0.1.0',
            'name': 'testing_plugin',
            'title': 'Test plugin',
            'package_version': '1.0.0',
            'description': 'Enable to use plugin X for Neutron',
            'fuel_version': ['6.0'],
            'groups': [],
            'licenses': ['License 1'],
            'authors': ['Author1'],
            'homepage': 'http://some-plugin-url.com/',
            'is_hotpluggable': False,
            'releases': [
                {'repository_path': 'repositories/ubuntu',
                 'version': '2014.2-6.0', 'os': 'ubuntu',
                 'mode': ['ha', 'multinode'],
                 'deployment_scripts_path': 'deployment_scripts/'},
                {'repository_path': 'repositories/centos',
                 'version': '2014.2-6.0', 'os': 'centos',
                 'mode': ['ha', 'multinode'],
                 'deployment_scripts_path': 'deployment_scripts/'},
                {'repository_path': 'repositories/ubuntu',
                 'version': '2015.1-8.0', 'os': 'ubuntu',
                 'mode': ['ha', 'multinode'],
                 'deployment_scripts_path': 'deployment_scripts/'},
            ]
        }

        sample_plugin.update(kwargs)
        return sample_plugin

    def get_default_components(self, **kwargs):
        default_components = [
            {
                'name': 'hypervisor:test_hypervisor',
                'compatible': [
                    {'name': 'hypervisor:*'},
                    {'name': 'storage:object:block:swift'}
                ],
                'incompatible': [
                    {'name': 'network:*'},
                    {'name': 'additional_service:*'}
                ]
            }
        ]

        default_components[0].update(kwargs)
        return default_components

    def get_default_vmware_attributes_metadata(self):
        return self.read_fixtures(
            ['openstack'])[0]['fields']['vmware_attributes_metadata']

    def upload_fixtures(self, fxtr_names):
        for fxtr_path in self.fxtr_paths_by_names(fxtr_names):
            with open(fxtr_path, "r") as fxtr_file:
                upload_fixture(fxtr_file)

    def read_fixtures(self, fxtr_names):
        data = []
        for fxtr_path in self.fxtr_paths_by_names(fxtr_names):
            with open(fxtr_path, "r") as fxtr_file:
                try:
                    data.extend(load_fixture(fxtr_file))
                except Exception as exc:
                    logger.error(
                        'Error "%s" occurred while loading '
                        'fixture %s' % (exc, fxtr_path)
                    )
        return data

    def fxtr_paths_by_names(self, fxtr_names):
        for fxtr in fxtr_names:
            for ext in ['json', 'yaml']:
                fxtr_path = os.path.join(
                    self.fixture_dir,
                    "%s.%s" % (fxtr, ext)
                )

                if os.path.exists(fxtr_path):
                    logger.debug(
                        "Fixture file is found, yielding path: %s",
                        fxtr_path
                    )
                    yield fxtr_path
                    break
            else:
                logger.warning(
                    "Fixture file was not found: %s",
                    fxtr
                )

    def find_item_by_pk_model(self, data, pk, model):
        for item in data:
            if item.get('pk') == pk and item.get('model') == model:
                return item

    def _get_cluster_by_id(self, cluster_id):
        """Get cluster by cluster ID.

        Get cluster by cluster ID. If `cluster_id` is `None` then return
        first cluster from the list.

        :param cluster_id: cluster ID
        :type cluster_id: int
        :return: cluster
        """
        if cluster_id is None:
            return self.clusters[0]

        for cluster in self.clusters:
            if cluster.id == cluster_id:
                return cluster

        raise Exception(
            'Cluster with ID "{0}" was not found.'.format(cluster_id))

    def launch_provisioning_selected(self, nodes_uids=None, cluster_id=None):
        if self.clusters:
            cluster = self._get_cluster_by_id(cluster_id)
            if not nodes_uids:
                nodes_uids = [n.uid for n in cluster.nodes]
            action_url = reverse(
                'ProvisionSelectedNodes',
                kwargs={'cluster_id': cluster.id}
            ) + '?nodes={0}'.format(','.join(nodes_uids))
            resp = self.app.put(
                action_url,
                '{}',
                headers=self.default_headers,
                expect_errors=True
            )
            self.tester.assertEqual(202, resp.status_code)
            response = resp.json_body
            return self.db.query(Task).filter_by(
                uuid=response['uuid']
            ).first()
        else:
            raise NotImplementedError(
                "Nothing to provision - try creating cluster"
            )

    def launch_deployment(self, cluster_id=None):
        if self.clusters:
            cluster_id = self._get_cluster_by_id(cluster_id).id
            resp = self.app.put(
                reverse(
                    'ClusterChangesHandler',
                    kwargs={'cluster_id': cluster_id}),
                headers=self.default_headers)

            return self.db.query(Task).filter_by(
                uuid=resp.json_body['uuid']
            ).first()
        else:
            raise NotImplementedError(
                "Nothing to deploy - try creating cluster"
            )

    def stop_deployment(self, cluster_id=None):
        if self.clusters:
            cluster_id = self._get_cluster_by_id(cluster_id).id
            resp = self.app.put(
                reverse(
                    'ClusterStopDeploymentHandler',
                    kwargs={'cluster_id': cluster_id}),
                expect_errors=True,
                headers=self.default_headers)

            return self.db.query(Task).filter_by(
                uuid=resp.json_body['uuid']
            ).first()
        else:
            raise NotImplementedError(
                "Nothing to stop - try creating cluster"
            )

    def reset_environment(self, expect_http=None, cluster_id=None):
        if self.clusters:
            cluster_id = self._get_cluster_by_id(cluster_id).id
            resp = self.app.put(
                reverse(
                    'ClusterResetHandler',
                    kwargs={'cluster_id': cluster_id}),
                expect_errors=True,
                headers=self.default_headers)
            if expect_http is not None:
                self.tester.assertEqual(resp.status_code, expect_http)
            else:
                # if task was started status code can be either 200 or 202
                # depending on task status
                self.tester.assertIn(resp.status_code, [200, 202])
            if not (200 <= resp.status_code < 400):
                return resp.body
            return self.db.query(Task).filter_by(
                uuid=resp.json_body['uuid']
            ).first()
        else:
            raise NotImplementedError(
                "Nothing to reset - try creating cluster"
            )

    def delete_environment(self, expect_http=202, cluster_id=None):
        if self.clusters:
            cluster_id = self._get_cluster_by_id(cluster_id).id
            resp = self.app.delete(
                reverse(
                    'ClusterHandler',
                    kwargs={'obj_id': cluster_id}),
                expect_errors=True,
                headers=self.default_headers)
            self.tester.assertEqual(resp.status_code, expect_http)
            if not str(expect_http).startswith("2"):
                return resp.body
            return self.db.query(Task).filter_by(
                name=consts.TASK_NAMES.cluster_deletion
            ).first()
        else:
            raise NotImplementedError(
                "Nothing to delete - try creating cluster"
            )

    def launch_verify_networks(self, data=None, expect_errors=False,
                               cluster_id=None):
        if self.clusters:
            cluster = self._get_cluster_by_id(cluster_id)
            net_urls = {
                "nova_network": {
                    "config": "NovaNetworkConfigurationHandler",
                    "verify": "NovaNetworkConfigurationVerifyHandler"
                },
                "neutron": {
                    "config": "NeutronNetworkConfigurationHandler",
                    "verify": "NeutronNetworkConfigurationVerifyHandler"
                }
            }
            provider = cluster.net_provider
            if data:
                nets = jsonutils.dumps(data)
            else:
                resp = self.app.get(
                    reverse(
                        net_urls[provider]["config"],
                        kwargs={'cluster_id': cluster.id}
                    ),
                    headers=self.default_headers
                )
                self.tester.assertEqual(200, resp.status_code)
                nets = resp.body

            resp = self.app.put(
                reverse(
                    net_urls[provider]["verify"],
                    kwargs={'cluster_id': cluster.id}),
                nets,
                headers=self.default_headers,
                expect_errors=expect_errors,
            )
            if expect_errors:
                return resp
            else:
                task_uuid = resp.json_body['uuid']
                return self.db.query(Task).filter_by(uuid=task_uuid).first()
        else:
            raise NotImplementedError(
                "Nothing to verify - try creating cluster"
            )

    def make_bond_via_api(self, bond_name, bond_mode, nic_names, node_id=None,
                          bond_properties=None, interface_properties=None):
        if not node_id:
            node_id = self.nodes[0]["id"]
        resp = self.app.get(
            reverse("NodeNICsHandler",
                    kwargs={"node_id": node_id}),
            headers=self.default_headers)
        self.tester.assertEqual(resp.status_code, 200)
        data = resp.json_body

        nics = self.db.query(NodeNICInterface).filter(
            NodeNICInterface.name.in_(nic_names)
        ).filter(
            NodeNICInterface.node_id == node_id
        )
        self.tester.assertEqual(nics.count(), len(nic_names))

        assigned_nets, slaves = [], []
        for nic in data:
            if nic['name'] in nic_names:
                assigned_nets.extend(nic['assigned_networks'])
                slaves.append({'name': nic['name']})
                nic['assigned_networks'] = []
        bond_dict = {
            "name": bond_name,
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": bond_mode,
            "slaves": slaves,
            "assigned_networks": assigned_nets
        }
        if bond_properties:
            bond_dict["bond_properties"] = bond_properties
        if interface_properties:
            bond_dict["interface_properties"] = interface_properties
        data.append(bond_dict)
        resp = self.node_nics_put(node_id, data)
        self.tester.assertEqual(resp.status_code, 200)

    def refresh_nodes(self):
        for n in self.nodes[:]:
            try:
                self.db.add(n)
                self.db.refresh(n)
            except Exception:
                self.nodes.remove(n)
        self.db.flush()

    def refresh_clusters(self):
        for n in self.clusters[:]:
            try:
                self.db.refresh(n)
            except Exception:
                self.nodes.remove(n)

    def _wait_task_status(self, task, timeout, wait_until_in_statuses):
        timer = time.time()
        while task.status in wait_until_in_statuses:
            self.db.refresh(task)
            if time.time() - timer > timeout:
                raise Exception(
                    "Task '{0}' seems to be hanged".format(
                        task.name
                    )
                )
            time.sleep(1)

    def _wait_task(self, task, timeout, message):
        wait_until_in_statuses = (consts.TASK_STATUSES.running,
                                  consts.TASK_STATUSES.pending)
        self._wait_task_status(task, timeout, wait_until_in_statuses)
        if isinstance(message, self._regex_type):
            self.tester.assertRegexpMatches(task.message, message)
        elif isinstance(message, six.string_types):
            self.tester.assertEqual(task.message, message)

    def wait_ready(self, task, timeout=60, message=None):
        self._wait_task(task, timeout, message)
        self.tester.assertEqual(task.status, consts.TASK_STATUSES.ready)

    def wait_until_task_pending(self, task, timeout=60):
        wait_until_in_statuses = (consts.TASK_STATUSES.pending,)
        self._wait_task_status(task, timeout,
                               wait_until_in_statuses=wait_until_in_statuses)
        self.tester.assertNotEqual(task.status, consts.TASK_STATUSES.pending)

    def wait_error(self, task, timeout=60, message=None):
        self._wait_task(task, timeout, message)
        self.tester.assertEqual(task.status, consts.TASK_STATUSES.error)

    def wait_for_nodes_status(self, nodes, status):
        def check_statuses():
            self.refresh_nodes()

            nodes_with_status = filter(
                lambda x: x.status in status,
                nodes)

            return len(nodes) == len(nodes_with_status)

        self.wait_for_true(
            check_statuses,
            error_message='Something wrong with the statuses')

    def wait_for_true(self, check, args=[], kwargs={},
                      timeout=60, error_message='Timeout error'):

        start_time = time.time()

        while True:
            result = check(*args, **kwargs)
            if result:
                return result
            if time.time() - start_time > timeout:
                raise TimeoutError(error_message)
            time.sleep(0.1)

    def _api_get(self, method, instance_id, expect_errors=False):
        return self.app.get(
            reverse(method,
                    kwargs=instance_id),
            headers=self.default_headers,
            expect_errors=expect_errors)

    def _api_put(self, method, instance_id, data, expect_errors=False):
        return self.app.put(
            reverse(method,
                    kwargs=instance_id),
            jsonutils.dumps(data),
            headers=self.default_headers,
            expect_errors=expect_errors)

    def nova_networks_get(self, cluster_id, expect_errors=False):
        return self._api_get('NovaNetworkConfigurationHandler',
                             {'cluster_id': cluster_id},
                             expect_errors)

    def nova_networks_put(self, cluster_id, networks, expect_errors=False):
        return self._api_put('NovaNetworkConfigurationHandler',
                             {'cluster_id': cluster_id},
                             networks,
                             expect_errors)

    def neutron_networks_get(self, cluster_id, expect_errors=False):
        return self._api_get('NeutronNetworkConfigurationHandler',
                             {'cluster_id': cluster_id},
                             expect_errors)

    def neutron_networks_put(self, cluster_id, networks, expect_errors=False):
        return self._api_put('NeutronNetworkConfigurationHandler',
                             {'cluster_id': cluster_id},
                             networks,
                             expect_errors)

    def cluster_changes_put(self, cluster_id, expect_errors=False):
        return self._api_put('ClusterChangesHandler',
                             {'cluster_id': cluster_id},
                             [],
                             expect_errors)

    def node_nics_get(self, node_id, expect_errors=False):
        return self._api_get('NodeNICsHandler',
                             {'node_id': node_id},
                             expect_errors)

    def node_nics_put(self, node_id, interfaces, expect_errors=False):
        return self._api_put('NodeNICsHandler',
                             {'node_id': node_id},
                             interfaces,
                             expect_errors)

    def node_collection_nics_put(self, nodes,
                                 expect_errors=False):
        return self._api_put('NodeCollectionNICsHandler',
                             {},
                             nodes,
                             expect_errors)

    def _create_network_group(self, expect_errors=False, cluster=None,
                              **kwargs):
        if not cluster:
            cluster = self.clusters[0]
        ng = {
            "release": cluster.release.id,
            "name": "external",
            "vlan_start": 50,
            "cidr": "10.3.0.0/24",
            "gateway": "10.3.0.1",
            "group_id": Cluster.get_default_group(cluster).id,
            "meta": {
                "notation": consts.NETWORK_NOTATION.cidr,
                "use_gateway": True,
                "map_priority": 2}
        }
        ng.update(kwargs)
        resp = self.app.post(
            reverse('NetworkGroupCollectionHandler'),
            jsonutils.dumps(ng),
            headers=self.default_headers,
            expect_errors=expect_errors,
        )
        return resp

    def _update_network_group(self, ng_data, expect_errors=False):
        return self.app.put(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': ng_data['id']}
            ),
            jsonutils.dumps(ng_data),
            headers=self.default_headers,
            expect_errors=expect_errors
        )

    def _set_additional_component(self, cluster, component, value):
        attrs = copy.deepcopy(cluster.attributes.editable)
        attrs['additional_components'][component]['value'] = value

        self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster.id}),
            params=jsonutils.dumps({'editable': attrs}),
            headers=self.default_headers
        )

    def _delete_network_group(self, ng_id, expect_errors=False):
        return self.app.delete(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': ng_id}
            ),
            headers=self.default_headers,
            expect_errors=False
        )

    def _add_plugin_network_roles(self, cluster, network_roles):
        plugin_data = self.get_default_plugin_metadata(releases=[{
            'repository_path': 'repositories/ubuntu',
            'version': cluster.release.version,
            'os': cluster.release.operating_system.lower(),
            'mode': [cluster.mode],
        }])
        plugin_data['network_roles_metadata'] = network_roles
        plugin = Plugin.create(plugin_data)
        ClusterPlugins.set_attributes(cluster.id, plugin.id, enabled=True)
        return plugin


class BaseTestCase(TestCase):

    fixtures = ['admin_network', 'master_node_settings']

    def __init__(self, *args, **kwargs):
        super(BaseTestCase, self).__init__(*args, **kwargs)
        self.default_headers = {
            "Content-Type": "application/json"
        }

    @classmethod
    def setUpClass(cls):
        cls.app = app.TestApp(
            build_app(db_driver=test_db_driver).wsgifunc(
                ConnectionMonitorMiddleware)
        )
        syncdb()

    def setUp(self):
        self.db = db
        flush()
        self.env = EnvironmentManager(app=self.app, session=self.db)
        self.env.upload_fixtures(self.fixtures)

    def tearDown(self):
        self.db.remove()

    def assertNotRaises(self, exception, method, *args, **kwargs):
        try:
            method(*args, **kwargs)
        except exception:
            self.fail('Exception "{0}" raised.'.format(exception))

    def assertRaisesWithMessage(self, exc, msg, func, *args, **kwargs):
        try:
            func(*args, **kwargs)
            self.assertFail()
        except Exception as inst:
            self.assertIsInstance(inst, exc)
            self.assertEqual(inst.message, msg)

    def assertRaisesWithMessageIn(self, exc, msg, func, *args, **kwargs):
        try:
            func(*args, **kwargs)
            self.assertFail()
        except Exception as inst:
            self.assertIsInstance(inst, exc)
            self.assertIn(msg, inst.message)

    def assertValidJSON(self, data):
        self.assertNotRaises(ValueError, jsonutils.loads, data)

    def datadiff(self, data1, data2, path=None, ignore_keys=[],
                 compare_sorted=False):
        if path is None:
            path = []

        def fail(msg, failed_path):
            self.fail('Path "{0}": {1}'.format("->".join(failed_path), msg))

        if not isinstance(data1, dict) or not isinstance(data2, dict):
            if isinstance(data1, (list, tuple)):
                newpath = path[:]
                if compare_sorted:
                    data1 = sorted(data1)
                    data2 = sorted(data2)
                for i, keys in enumerate(izip(data1, data2)):
                    newpath.append(str(i))
                    self.datadiff(keys[0], keys[1], newpath, ignore_keys,
                                  compare_sorted)
                    newpath.pop()
            elif data1 != data2:
                err = "Values differ: {0} != {1}".format(
                    str(data1),
                    str(data2)
                )
                fail(err, path)
        else:
            newpath = path[:]

            if len(data1) != len(data2):
                fail('Dicts have different keys number: {0} != {1}'.format(
                    len(data1), len(data2)), path)

            for key1, key2 in zip(
                sorted(data1),
                sorted(data2)
            ):
                if key1 != key2:
                    err = "Keys differ: {0} != {1}".format(
                        str(key1),
                        str(key2)
                    )
                    fail(err, path)
                if key1 in ignore_keys:
                    continue
                newpath.append(key1)
                self.datadiff(data1[key1], data2[key2], newpath, ignore_keys,
                              compare_sorted)
                newpath.pop()


class BaseIntegrationTest(BaseTestCase):

    def tearDown(self):
        self._wait_for_threads()
        super(BaseIntegrationTest, self).tearDown()

    @classmethod
    def setUpClass(cls):
        super(BaseIntegrationTest, cls).setUpClass()
        nailgun.task.task.logs_utils.prepare_syslog_dir = mock.Mock()

    @classmethod
    def tearDownClass(cls):
        super(BaseIntegrationTest, cls).tearDownClass()

    def _wait_for_threads(self):
        # wait for fake task thread termination
        import threading
        for thread in threading.enumerate():
            if thread is not threading.currentThread():
                if hasattr(thread, "rude_join"):
                    timer = time.time()
                    timeout = 25
                    thread.rude_join(timeout)
                    if time.time() - timer > timeout:
                        raise Exception(
                            '{0} seconds is not enough'
                            ' - possible hanging'.format(
                                timeout
                            )
                        )


class BaseAuthenticationIntegrationTest(BaseIntegrationTest):

    @classmethod
    def setUpClass(cls):
        super(BaseAuthenticationIntegrationTest, cls).setUpClass()
        cls.app = app.TestApp(build_app(db_driver=test_db_driver).wsgifunc(
            ConnectionMonitorMiddleware, NailgunFakeKeystoneAuthMiddleware))
        syncdb()

    def get_auth_token(self):
        resp = self.app.post(
            '/keystone/v2.0/tokens',
            jsonutils.dumps({
                'auth': {
                    'tenantName': 'admin',
                    'passwordCredentials': {
                        'username': settings.FAKE_KEYSTONE_USERNAME,
                        'password': settings.FAKE_KEYSTONE_PASSWORD,
                    },
                },
            })
        )

        return resp.json['access']['token']['id'].encode('utf-8')


class BaseUnitTest(TestCase):
    pass


def fake_tasks(fake_rpc=True,
               mock_rpc=True,
               tick_count=100,
               tick_interval=0,
               **kwargs):
    def wrapper(func):
        func = mock.patch(
            'nailgun.task.task.settings.FAKE_TASKS',
            True
        )(func)
        func = mock.patch(
            'nailgun.task.fake.settings.FAKE_TASKS_TICK_COUNT',
            tick_count
        )(func)
        func = mock.patch(
            'nailgun.task.fake.settings.FAKE_TASKS_TICK_INTERVAL',
            tick_interval
        )(func)
        if fake_rpc:
            func = mock.patch(
                'nailgun.task.task.rpc.cast',
                partial(
                    nailgun.task.task.fake_cast,
                    **kwargs
                )
            )(func)
        elif mock_rpc:
            func = mock.patch(
                'nailgun.task.task.rpc.cast',
                **kwargs
            )(func)
        return func
    return wrapper


class DeploymentTasksTestMixin(object):

    def _compare_tasks(self, reference, result):
        """Compare deployment tasks.

        Considering legacy format and compatible validator output with extra
        fields where legacy fields is converted to new syntax.

        :param reference: list of tasks
        :type reference: list
        :param result: list of tasks
        :type result: list
        """
        reference.sort(key=lambda x: x.get('id', x.get('task_name')))
        result.sort(key=lambda x: x.get('id', x.get('task_name')))
        for ref, res in six.moves.zip(reference, result):
            for field in ref:
                if field == '_custom':
                    # unpack custom json fields if persist
                    self.assertEqual(
                        jsonutils.loads(ref.get(field)),
                        jsonutils.loads((res or {}).get(field))
                    )
                else:
                    self.assertEqual(ref.get(field), (res or {}).get(field))


# this method is for development and troubleshooting purposes
def datadiff(data1, data2, branch, p=True):
    def iterator(data1, data2):
        if isinstance(data1, (list,)) and isinstance(data2, (list,)):
            return range(max(len(data1), len(data2)))
        elif isinstance(data1, (dict,)) and isinstance(data2, (dict,)):
            return (set(data1.keys()) | set(data2.keys()))
        else:
            raise TypeError

    diff = []
    if data1 != data2:
        try:
            it = iterator(data1, data2)
        except Exception:
            return [(branch, data1, data2)]

        for k in it:
            newbranch = branch[:]
            newbranch.append(k)

            if p:
                print("Comparing branch: %s" % newbranch)
            try:
                try:
                    v1 = data1[k]
                except (KeyError, IndexError):
                    if p:
                        print("data1 seems does not have key = %s" % k)
                    diff.append((newbranch, None, data2[k]))
                    continue
                try:
                    v2 = data2[k]
                except (KeyError, IndexError):
                    if p:
                        print("data2 seems does not have key = %s" % k)
                    diff.append((newbranch, data1[k], None))
                    continue

            except Exception:
                if p:
                    print("data1 and data2 cannot be compared on "
                          "branch: %s" % newbranch)
                return diff.append((newbranch, data1, data2))

            else:
                if v1 != v2:
                    if p:
                        print("data1 and data2 do not match "
                              "each other on branch: %s" % newbranch)
                        # print("data1 = %s" % data1)
                        print("v1 = %s" % v1)
                        # print("data2 = %s" % data2)
                        print("v2 = %s" % v2)
                    diff.extend(datadiff(v1, v2, newbranch))
    return diff


def reflect_db_metadata():
    meta = sa.MetaData()
    meta.reflect(bind=db.get_bind())
    return meta


def get_nodegroup_network_schema_template(template, group_name):
    custom_template = template['adv_net_template'][group_name]
    custom_template_obj = NetworkTemplate(jsonutils.dumps(custom_template))
    node_custom_template = custom_template_obj.safe_substitute(
        custom_template['nic_mapping']['default'])
    return jsonutils.loads(node_custom_template)['network_scheme']


class BaseAlembicMigrationTest(TestCase):

    def setUp(self):
        super(BaseAlembicMigrationTest, self).setUp()
        self.meta = reflect_db_metadata()

    def tearDown(self):
        db.remove()
        super(BaseAlembicMigrationTest, self).tearDown()


class BaseMasterNodeSettignsTest(BaseIntegrationTest):

    def setUp(self):
        super(BaseMasterNodeSettignsTest, self).setUp()
        self.create_master_node_settings()

    master_node_settings_template = {
        "settings": {
            "ui_settings": {
                "view_mode": "standard",
                "filter": {},
                "sort": [{"status": "asc"}],
                "filter_by_labels": {},
                "sort_by_labels": [],
                "search": ""
            },
            "statistics": {
                "send_anonymous_statistic": {
                    "type": "checkbox",
                    "value": True,
                    "label": "statistics.setting_labels."
                             "send_anonymous_statistic",
                    "weight": 10
                },
                "user_choice_saved": {
                    "type": "hidden",
                    "value": False
                }
            }
        }
    }

    def create_master_node_settings(self):
        self.master_node_settings = {
            'master_node_uid': str(uuid.uuid4()),
        }
        self.master_node_settings.update(self.master_node_settings_template)
        MasterNodeSettings.create(self.master_node_settings)
        self.db.commit()

    def set_sending_stats(self, value):
        mn_settings = MasterNodeSettings.get_one()
        mn_settings.settings = dict_merge(
            mn_settings.settings,
            {'statistics': {
                'user_choice_saved': {'value': True},
                'send_anonymous_statistic': {'value': value}
            }})
        self.db.flush()

    def enable_sending_stats(self):
        self.set_sending_stats(True)

    def disable_sending_stats(self):
        self.set_sending_stats(False)


class BaseValidatorTest(BaseTestCase):
    """JSON-schema validation policy:

       1) All required properties are present;
       2) No additional properties allowed;
       3) Item has correct type.
    """
    validator = None

    def serialize(self, data):
        """Serialize object to a string.

        :param data: object being serialized
        :return: stringified JSON-object
        """
        return jsonutils.dumps(data)

    def get_invalid_data_context(self, data, *args):
        """Returns context object of raised InvalidData exception.

        :return: context of 'errors.InvalidData'
        """
        serialized_data = self.serialize(data)
        with self.assertRaises(errors.InvalidData) as context:
            self.validator(serialized_data, *args)

        return context

    def assertRaisesAdditionalProperty(self, obj, key, *args):
        context = self.get_invalid_data_context(obj, *args)

        self.assertIn(
            "Additional properties are not allowed".format(key),
            context.exception.message)

        self.assertIn(
            "'{0}' was unexpected".format(key),
            context.exception.message)

    def assertRaisesRequiredProperty(self, obj, key):
        context = self.get_invalid_data_context(obj)

        self.assertIn(
            "Failed validating 'required' in schema",
            context.exception.message)

        self.assertIn(
            "'{0}' is a required property".format(key),
            context.exception.message)

    def assertRaisesInvalidType(self, obj, value, expected_value):
        context = self.get_invalid_data_context(obj)
        self.assertIn(
            "Failed validating 'type' in schema",
            context.exception.message)
        self.assertIn(
            "{0} is not of type {1}".format(value, expected_value),
            context.exception.message)

    def assertRaisesInvalidAnyOf(self, obj, passed_value, instance):
        context = self.get_invalid_data_context(obj)
        self.assertIn(
            "Failed validating 'anyOf' in schema",
            context.exception.message)

        err_msg = "{0} is not valid under any of the given schemas"
        self.assertIn(
            err_msg.format(passed_value),
            context.exception.message)

        self.assertIn(
            "On instance{0}".format(instance),
            context.exception.message)

    def assertRaisesInvalidOneOf(self, passed_data,
                                 incorrect, data_label, *args):
        """Check raised within error context exception

        Test that the exception has features pertaining to
        failed 'oneOf' validation case of jsonschema

        :param passed_data: dict to be serialized and passed for validation
        :param incorrect: data value which doesn't pass the validation
            and is present in error message of original exception
        :param data_label: key name from passed_data one of which value
            doesn't pass the validation; is present in the error message
        :param *args: list of additional arguments passed to validation code

        """
        context = self.get_invalid_data_context(passed_data, *args)
        self.assertIn(
            "Failed validating 'oneOf' in schema",
            context.exception.message)

        err_msg = "{0} is not valid under any of the given schemas"
        self.assertIn(
            err_msg.format(incorrect),
            context.exception.message)

        self.assertIn(
            "On instance{0}".format(data_label),
            context.exception.message)

    def assertRaisesInvalidEnum(self, obj, value, expected_value):
        context = self.get_invalid_data_context(obj)
        self.assertIn(
            "Failed validating 'enum' in schema",
            context.exception.message)
        self.assertIn(
            "{0} is not one of {1}".format(value, expected_value),
            context.exception.message)

    def assertRaisesTooLong(self, obj, stringified_values):
        context = self.get_invalid_data_context(obj)
        self.assertIn(
            "{0} is too long".format(stringified_values),
            context.exception.message)

    def assertRaisesTooShort(self, obj, stringified_values):
        context = self.get_invalid_data_context(obj)
        self.assertIn(
            "{0} is too short".format(stringified_values),
            context.exception.message)

    def assertRaisesNonUnique(self, obj, stringified_values):
        context = self.get_invalid_data_context(obj)
        self.assertIn(
            "{0} has non-unique elements".format(stringified_values),
            context.exception.message)

    def assertRaisesLessThanMinimum(self, obj, stringified_values):
        context = self.get_invalid_data_context(obj)
        self.assertIn(
            "{0} is less than the minimum".format(stringified_values),
            context.exception.message)

    def assertRaisesGreaterThanMaximum(self, obj, stringified_values):
        context = self.get_invalid_data_context(obj)
        self.assertIn(
            "{0} is greater than the maximum".format(stringified_values),
            context.exception.message)

    def assertRaisesNotMatchPattern(self, obj, stringified_values):
        context = self.get_invalid_data_context(obj)
        self.assertIn(
            "Failed validating 'pattern' in schema",
            context.exception.message)
        self.assertIn(
            "{0} does not match".format(stringified_values),
            context.exception.message)
