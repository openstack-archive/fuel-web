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

"""Provisioning serializers for orchestrator"""

from itertools import groupby

import netaddr
import six

from nailgun import consts
from nailgun.extensions import fire_callback_on_provisioning_data_serialization
from nailgun.extensions import node_extension_call
from nailgun.logger import logger
from nailgun import objects
from nailgun.orchestrator.base_serializers import MellanoxMixin
from nailgun.orchestrator.priority_serializers import PriorityStrategy
from nailgun.orchestrator import tasks_templates
from nailgun.settings import settings
from nailgun import utils


class ProvisioningSerializer(MellanoxMixin):
    """Provisioning serializer"""

    @classmethod
    def serialize(cls, cluster, nodes, ignore_customized=False):
        """Serialize cluster for provisioning."""

        cluster_attrs = objects.Attributes.merged_attrs_values(
            cluster.attributes
        )
        serialized_nodes = []
        for customized, node_group in groupby(
                nodes, lambda node: bool(node.replaced_provisioning_info)):

            if customized and not ignore_customized:
                serialized_nodes.extend(cls.serialize_customized(node_group))
            else:
                serialized_nodes.extend(
                    cls.serialize_nodes(cluster_attrs, node_group))

        serialized_info = (cluster.replaced_provisioning_info or
                           cls.serialize_cluster_info(cluster_attrs, nodes))
        serialized_info['fault_tolerance'] = cls.fault_tolerance(cluster,
                                                                 nodes)
        serialized_info['nodes'] = serialized_nodes
        return serialized_info

    @classmethod
    def serialize_cluster_info(cls, cluster_attrs, nodes):
        return {
            'engine': {
                'url': settings.COBBLER_URL,
                'username': settings.COBBLER_USER,
                'password': settings.COBBLER_PASSWORD,
                'master_ip': settings.MASTER_IP,
            }}

    @classmethod
    def serialize_customized(self, nodes):
        serialized = []
        for node in nodes:
            serialized.append(node.replaced_provisioning_info)
        return serialized

    @classmethod
    def serialize_nodes(cls, cluster_attrs, nodes):
        """Serialize nodes."""
        serialized_nodes = []
        for node in nodes:
            serialized_nodes.append(cls.serialize_node(cluster_attrs, node))
        return serialized_nodes

    @classmethod
    def serialize_cloud_init_templates(cls, release):
        """Serialize a dict of cloud-init templates.

        It will serialize the names of cloud-init templates, thus allowing
        nailgun to request particular version for every template to be
        rendered during provisioning.
        Eg.:
        "cloud_init_templates": {
            "boothook": "boothook_fuel_6.1_centos.jinja2",
            "cloud_config": "cloud_config_fuel_6.1_centos.jinja2",
            "meta_data": "meta_data_fuel_6.1_centos.jinja2",
        }
        """
        cloud_init_templates = {}
        for k in (consts.CLOUD_INIT_TEMPLATES.boothook,
                  consts.CLOUD_INIT_TEMPLATES.cloud_config,
                  consts.CLOUD_INIT_TEMPLATES.meta_data):
            cloud_init_templates[k] = '{0}_fuel_{1}_{2}.jinja2'.format(
                k, release.environment_version,
                release.operating_system.lower())
        return cloud_init_templates

    @classmethod
    def serialize_node(cls, cluster_attrs, node):
        """Serialize a single node."""
        serialized_node = {
            'uid': node.uid,
            'power_address': node.ip,
            'name': objects.Node.get_slave_name(node),
            # right now it duplicates to avoid possible issues
            'slave_name': objects.Node.get_slave_name(node),
            'hostname': objects.Node.get_node_fqdn(node),
            'power_pass': cls.get_ssh_key_path(node),

            'profile': cluster_attrs['cobbler']['profile'],
            'power_type': 'ssh',
            'power_user': 'root',
            'name_servers': '\"%s\"' % settings.DNS_SERVERS,
            'name_servers_search': '\"%s\"' % settings.DNS_SEARCH,
            'netboot_enabled': '1',
            # For provisioning phase
            'kernel_options': {
                'netcfg/choose_interface':
                objects.Node.get_admin_physical_iface(node).mac,
                'udevrules': cls.interfaces_mapping_for_udev(node)},
            'ks_meta': {
                'pm_data': {
                    'ks_spaces': node_extension_call('get_node_volumes', node),
                    'kernel_params': objects.Node.get_kernel_params(node)},
                'fuel_version': node.cluster.fuel_version,
                'cloud_init_templates':
                cls.serialize_cloud_init_templates(node.cluster.release),
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

                # NOTE(aroma): identity parameter usually is added/updated
                # by nailgun agent but due to particularities of its execution
                # flow such action may lead to deployment failures [1].
                # Hence we supply the information here so fuel-agent will
                # create mcollective config initially with the data present,
                # [1]: https://bugs.launchpad.net/fuel/+bug/1518306
                'mco_identity': node.id,

                'auth_key': "\"%s\"" % cluster_attrs.get('auth_key', ''),
                'authorized_keys':
                ["\"%s\"" % key for key in settings.AUTHORIZED_KEYS],
                'master_ip': settings.MASTER_IP,
                'timezone': settings.TIMEZONE,
            }}

        provision_data = cluster_attrs.get('provision')
        if provision_data:
            if provision_data['method'] == consts.PROVISION_METHODS.image:
                serialized_node['ks_meta']['image_data'] = \
                    provision_data['image_data']

        serialized_node['ks_meta']['repo_setup'] = cluster_attrs['repo_setup']

        vlan_splinters = cluster_attrs.get('vlan_splinters', {})
        if vlan_splinters.get('vswitch') == 'kernel_lt':
            serialized_node['ks_meta']['kernel_lt'] = 1

        cls.inject_mellanox_settings_for_provisioning(
            cluster_attrs, serialized_node)
        net_manager = objects.Cluster.get_network_manager(node.cluster)
        gw = net_manager.get_default_gateway(node.id)
        admin_net = objects.NetworkGroup.get_admin_network_group(node.id)
        serialized_node['ks_meta'].update({'gw': gw})
        serialized_node['ks_meta'].update(
            {'admin_net': admin_net.cidr}
        )

        serialized_node.update(cls.serialize_interfaces(node))

        return serialized_node

    @classmethod
    def serialize_interfaces(cls, node):
        interfaces = {}
        interfaces_extra = {}
        net_manager = objects.Cluster.get_network_manager(node.cluster)
        admin_ip = net_manager.get_admin_ip_for_node(node.id)
        admin_netmask = str(netaddr.IPNetwork(
            objects.NetworkGroup.get_admin_network_group(node.id).cidr
        ).netmask)

        for interface in node.nic_interfaces:
            name = interface.name

            interfaces[name] = {
                'mac_address': interface.mac,
                'static': '0'}

            # interfaces_extra field in cobbler ks_meta
            # means some extra data for network interfaces
            # configuration. It is used by cobbler snippet.
            # For example, cobbler interface model does not
            # have 'peerdns' field, but we need this field
            # to be configured. So we use interfaces_extra
            # branch in order to set this unsupported field.
            interfaces_extra[name] = {
                'peerdns': 'no',
                'onboot': 'no'}

            # We want node to be able to PXE boot via any of its
            # interfaces. That is why we add all discovered
            # interfaces into cobbler system. But we want
            # assignted fqdn to be resolved into one IP address
            # because we don't completely support multiinterface
            # configuration yet.
            if interface.mac == objects.Node.\
               get_admin_physical_iface(node).mac:
                interfaces[name]['dns_name'] = \
                    objects.Node.get_node_fqdn(node)
                interfaces[name]['netmask'] = admin_netmask
                interfaces[name]['ip_address'] = admin_ip
                interfaces_extra[name]['onboot'] = 'yes'

        return {
            'interfaces': interfaces,
            'interfaces_extra': interfaces_extra}

    @classmethod
    def interfaces_mapping_for_udev(cls, node):
        """Serialize interfaces mapping for cobbler

        :param node: node model
        :returns: returns string, example:
                  00:02:03:04:04_eth0,00:02:03:04:05_eth1
        """
        return ','.join((
            '{0}_{1}'.format(i.mac, i.name) for i in node.nic_interfaces))

    @classmethod
    def get_ssh_key_path(cls, node):
        """Assign power pass depend on node state."""
        if node.status == "discover":
            logger.info(
                u'Node %s seems booted with bootstrap image', node.full_name)
            return settings.PATH_TO_BOOTSTRAP_SSH_KEY

        logger.info(u'Node %s seems booted with real system', node.full_name)
        return settings.PATH_TO_SSH_KEY

    @classmethod
    def fault_tolerance(cls, cluster, nodes):
        may_fail = []
        roles_metadata = objects.Cluster.get_roles(cluster)
        for role in roles_metadata:
            if 'fault_tolerance' in roles_metadata[role]:
                tolerance = roles_metadata[role]['fault_tolerance']
                # only percantage is supported for now
                if not tolerance.endswith('%'):
                    continue
                percentage = tolerance[:-1]
                uids = []
                for node in nodes:
                    if role in node.roles:
                        uids.append(node.uid)
                may_fail.append({'uids': uids,
                                 'percentage': int(percentage)})
        return may_fail


class ProvisioningSerializer61(ProvisioningSerializer):

    @classmethod
    def serialize(cls, cluster, nodes, ignore_customized=False):
        serialized_info = super(ProvisioningSerializer61, cls).serialize(
            cluster, nodes, ignore_customized)
        serialized_info['pre_provision'] = \
            cls.serialize_pre_provision_tasks(cluster)
        return serialized_info

    @classmethod
    def serialize_pre_provision_tasks(cls, cluster):
        tasks = []
        attrs = objects.Attributes.merged_attrs_values(cluster.attributes)

        is_build_images = all([
            cluster.release.operating_system == consts.RELEASE_OS.ubuntu,
            attrs['provision']['method'] == consts.PROVISION_METHODS.image])

        if is_build_images:
            packages = cls._make_provisioning_package_list(attrs['provision'])
            tasks.append(
                tasks_templates.make_provisioning_images_task(
                    [consts.MASTER_NODE_UID],
                    attrs['repo_setup']['repos'],
                    attrs['provision'],
                    cluster.id,
                    packages))

        # NOTE(kozhukalov): This pre-provision task is going to be
        # removed by 7.0 because we need this only for classic way of
        # provision and only until we get rid of it. We are going
        # to download debian-installer initrd and kernel just before
        # starting actual provisioning.
        is_download_debian_installer = all([
            cluster.release.operating_system == consts.RELEASE_OS.ubuntu,
            attrs['provision']['method'] == consts.PROVISION_METHODS.cobbler])

        if is_download_debian_installer:
            tasks.append(
                tasks_templates.make_download_debian_installer_task(
                    [consts.MASTER_NODE_UID],
                    attrs['repo_setup']['repos'],
                    attrs['repo_setup']['installer_kernel'],
                    attrs['repo_setup']['installer_initrd']))

        PriorityStrategy().one_by_one(tasks)
        return tasks

    @classmethod
    def serialize_node(cls, cluster_attrs, node):
        serialized_node = super(ProvisioningSerializer61, cls).serialize_node(
            cluster_attrs, node)

        use_fedora = cluster_attrs.get('use_fedora_lt', {})
        if use_fedora.get('kernel') == 'fedora_lt_kernel':
            serialized_node['ks_meta']['kernel_lt'] = 1

        return serialized_node

    @classmethod
    def _make_provisioning_package_list(cls, provision_data):
        packages = provision_data.get('packages', '')
        return list(six.moves.filter(
            bool, (s.strip() for s in packages.split('\n'))))


def get_serializer_for_cluster(cluster):
    """Returns a serializer depends on a given `cluster`.

    :param cluster: cluster to process
    :returns: a serializer for a given cluster
    """
    serializers_map = {
        '5': ProvisioningSerializer,
        '6.0': ProvisioningSerializer,
        '6.1': ProvisioningSerializer61,
        '7.0': ProvisioningSerializer70,
        '8.0': ProvisioningSerializer80
    }

    for version, serializer in six.iteritems(serializers_map):
        if cluster.release.environment_version.startswith(version):
            return serializer

    # by default, we should return latest serializer
    return ProvisioningSerializer90


def _execute_pipeline(data, cluster, nodes, ignore_customized):
    "Executes pipelines depending on ignore_customized boolean."
    if ignore_customized:
        return fire_callback_on_provisioning_data_serialization(
            data, cluster, nodes)

    nodes_without_customized = {n.uid: n for n in nodes
                                if not n.replaced_provisioning_info}

    def keyfunc(node):
        return node['uid'] in nodes_without_customized

    temp_nodes = data['nodes']

    # not customized nodes
    data['nodes'] = list(six.moves.filter(keyfunc, temp_nodes))

    # NOTE(sbrzeczkowski): pipelines must be executed for nodes
    # which don't have replaced_provisioning_info specified
    updated_data = fire_callback_on_provisioning_data_serialization(
        data, cluster, list(six.itervalues(nodes_without_customized)))

    # customized nodes
    updated_data['nodes'].extend(six.moves.filterfalse(keyfunc, temp_nodes))

    return updated_data


def serialize(cluster, nodes, ignore_customized=False):
    """Serialize cluster for provisioning."""

    objects.Cluster.prepare_for_provisioning(cluster, nodes)
    serializer = get_serializer_for_cluster(cluster)

    data = serializer.serialize(
        cluster, nodes, ignore_customized=ignore_customized)

    return _execute_pipeline(data, cluster, nodes, ignore_customized)


class ProvisioningSerializer70(ProvisioningSerializer61):
    pass


class ProvisioningSerializer80(ProvisioningSerializer70):

    @classmethod
    def serialize_pre_provision_tasks(cls, cluster):
        tasks = super(ProvisioningSerializer80,
                      cls).serialize_pre_provision_tasks(cluster)

        attrs = objects.Attributes.merged_attrs_values(cluster.attributes)

        if attrs['ironic']['enabled']:
            tasks.append(
                tasks_templates.generate_ironic_bootstrap_keys_task(
                    [consts.MASTER_NODE_UID],
                    cluster.id))

            tasks.append(
                tasks_templates.make_ironic_bootstrap_task(
                    [consts.MASTER_NODE_UID],
                    cluster.id))

        PriorityStrategy().one_by_one(tasks)
        return tasks


class ProvisioningSerializer90(ProvisioningSerializer80):

    @classmethod
    def serialize_node(cls, cluster_attrs, node):
        serialized_node = super(ProvisioningSerializer90, cls).serialize_node(
            cluster_attrs, node)

        operator_user = cluster_attrs['operator_user']
        service_user = cluster_attrs['service_user']

        # Make sure that there are no empty strings as this might mess up
        # cloud init templates
        operator_user_sudo = utils.get_lines(operator_user['sudo'])
        operator_user_authkeys = utils.get_lines(operator_user['authkeys'])
        service_user_sudo = utils.get_lines(service_user['sudo'])

        root_password = service_user['root_password']

        operator_user_dict = {
            'name': operator_user['name'],
            'password': operator_user['password'],
            'homedir': operator_user['homedir'],
            'sudo': operator_user_sudo,
            'ssh_keys': operator_user_authkeys + settings.AUTHORIZED_KEYS,
        }
        service_user_dict = {
            'name': service_user['name'],
            'homedir': service_user['homedir'],
            'sudo': service_user_sudo,
            'password': service_user['password'],
            'ssh_keys': settings.AUTHORIZED_KEYS
        }
        root_user_dict = {
            'name': 'root',
            'homedir': '/root',
            'password': root_password,
            'ssh_keys': settings.AUTHORIZED_KEYS
        }

        serialized_node['ks_meta']['user_accounts'] = [operator_user_dict,
                                                       service_user_dict,
                                                       root_user_dict]

        return serialized_node
