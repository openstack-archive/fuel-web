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

from nailgun.logger import logger
from nailgun.network.manager import NetworkManager
from nailgun.settings import settings
from nailgun.task.helpers import TaskHelper


class ProvisioningSerializer(object):
    """Provisioning serializer"""

    @classmethod
    def serialize(cls, cluster, nodes):
        """Serialize cluster for provisioning."""

        cluster_attrs = cluster.attributes.merged_attrs_values()
        serialized_nodes = cls.serialize_nodes(cluster_attrs, nodes)

        return {
            'engine': {
                'url': settings.COBBLER_URL,
                'username': settings.COBBLER_USER,
                'password': settings.COBBLER_PASSWORD},
            'nodes': serialized_nodes}

    @classmethod
    def serialize_nodes(cls, cluster_attrs, nodes):
        """Serialize nodes."""
        serialized_nodes = []
        for node in nodes:
            serialized_node = cls.serialize_node(cluster_attrs, node)
            serialized_nodes.append(serialized_node)

        return serialized_nodes

    @classmethod
    def serialize_node(cls, cluster_attrs, node):
        """Serialize a single node."""

        serialized_node = {
            'uid': node.uid,
            'power_address': node.ip,
            'name': TaskHelper.make_slave_name(node.id),
            'hostname': node.fqdn,
            'power_pass': cls.get_ssh_key_path(node),

            'profile': cluster_attrs['cobbler']['profile'],
            'power_type': 'ssh',
            'power_user': 'root',
            'name_servers': '\"%s\"' % settings.DNS_SERVERS,
            'name_servers_search': '\"%s\"' % settings.DNS_SEARCH,
            'netboot_enabled': '1',
            'kernel_options': {
                'netcfg/choose_interface': node.admin_interface.mac,
                'udevrules': cls.interfaces_mapping_for_udev(node)},
            'ks_meta': {
                'ks_spaces': node.attributes.volumes,
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
                'auth_key': "\"%s\"" % cluster_attrs.get('auth_key', '')}}

        serialized_node.update(cls.serialize_interfaces(node))

        return serialized_node

    @classmethod
    def serialize_interfaces(cls, node):
        interfaces = {}
        interfaces_extra = {}
        net_manager = NetworkManager
        admin_ip = net_manager.get_admin_ip_for_node(node)
        admin_netmask = net_manager.get_admin_network_group().netmask

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
            if interface.mac == node.mac:
                interfaces[name]['dns_name'] = node.fqdn
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


def serialize(cluster, nodes):
    """Serialize cluster for provisioning."""
    TaskHelper.prepare_for_provisioning(nodes)

    return ProvisioningSerializer.serialize(cluster, nodes)
