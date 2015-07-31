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
from nailgun.extensions import node_extension_call
from nailgun.logger import logger
from nailgun import objects
from nailgun.orchestrator.priority_serializers import PriorityStrategy
from nailgun.orchestrator import tasks_templates
from nailgun.settings import settings


class ProvisioningSerializer(object):
    """Provisioning serializer"""

    @classmethod
    def serialize(cls, cluster, nodes, ignore_customized=False):
        """Serialize cluster for provisioning."""

        cluster_attrs = objects.Attributes.merged_attrs_values(
            cluster.attributes
        )
        serialized_nodes = []
        keyfunc = lambda node: bool(node.replaced_provisioning_info)
        for customized, node_group in groupby(nodes, keyfunc):
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

        mellanox_data = cluster_attrs.get('neutron_mellanox')
        if mellanox_data:
            serialized_node['ks_meta'].update({
                'mlnx_vf_num': mellanox_data['vf_num'],
                'mlnx_plugin_mode': mellanox_data['plugin'],
                'mlnx_iser_enabled': cluster_attrs['storage']['iser'],
            })
            # Add relevant kernel parameter when using Mellanox SR-IOV
            # and/or iSER (which works on top of a probed virtual function)
            # unless it was explicitly added by the user
            pm_data = serialized_node['ks_meta']['pm_data']
            if ((mellanox_data['plugin'] == 'ethernet' or
                    cluster_attrs['storage']['iser'] is True) and
                    'intel_iommu=' not in pm_data['kernel_params']):
                        pm_data['kernel_params'] += ' intel_iommu=on'

        net_manager = objects.Cluster.get_network_manager(node.cluster)
        gw = net_manager.get_default_gateway(node.id)
        serialized_node['ks_meta'].update({'gw': gw})
        serialized_node['ks_meta'].update(
            {'admin_net': net_manager.get_admin_network_group(node.id).cidr}
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
            net_manager.get_admin_network_group(node.id).cidr
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
            tasks.append(
                tasks_templates.make_provisioning_images_task(
                    [consts.MASTER_ROLE],
                    attrs['repo_setup']['repos'],
                    attrs['provision'],
                    cluster.id))

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
                    [consts.MASTER_ROLE],
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


def get_serializer_for_cluster(cluster):
    """Returns a serializer depends on a given `cluster`.

    :param cluster: cluster to process
    :returns: a serializer for a given cluster
    """
    serializers_map = {
        '5': ProvisioningSerializer,
        '6.0': ProvisioningSerializer,
    }

    for version, serializer in six.iteritems(serializers_map):
        if cluster.release.environment_version.startswith(version):
            return serializer

    # by default, we should return latest serializer
    return ProvisioningSerializer61


def serialize(cluster, nodes, ignore_customized=False):
    """Serialize cluster for provisioning."""
    objects.NodeCollection.prepare_for_provisioning(nodes)
    serializer = get_serializer_for_cluster(cluster)

    return serializer.serialize(
        cluster, nodes, ignore_customized=ignore_customized)
