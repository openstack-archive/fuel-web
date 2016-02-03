# -*- coding: utf-8 -*-

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

from nailgun import objects


class NailgunClusterAdapter(object):
    def __init__(self, cluster):
        self.cluster = cluster

    @classmethod
    def create(cls, data):
        cluster = objects.Cluster.create(data)
        return cls(cluster)

    @property
    def id(self):
        return self.cluster.id

    @property
    def name(self):
        return self.cluster.name

    @property
    def net_provider(self):
        return self.cluster.net_provider

    @property
    def release(self):
        return NailgunReleaseAdapter(self.cluster.release)

    @property
    def release_id(self):
        return self.cluster.release_id

    @property
    def pending_release_id(self):
        return self.cluster.pending_release_id

    @property
    def generated_attrs(self):
        return self.cluster.attributes.generated

    @generated_attrs.setter
    def generated_attrs(self, attrs):
        self.cluster.attributes.generated = attrs

    @property
    def editable_attrs(self):
        return self.cluster.attributes.editable

    @editable_attrs.setter
    def editable_attrs(self, attrs):
        self.cluster.attributes.editable = attrs

    def get_create_data(self):
        return objects.Cluster.get_create_data(self.cluster)

    def get_network_manager(self):
        net_manager = objects.Cluster.get_network_manager(
            instance=self.cluster)
        return NailgunNetworkManager(self.cluster, net_manager)

    def to_json(self):
        return objects.Cluster.to_json(self.cluster)

    @classmethod
    def get_by_uid(cls, cluster_id):
        cluster = objects.Cluster.get_by_uid(cluster_id)
        return cls(cluster)

    def get_network_groups(self):
        return (NailgunNetworkGroupAdapter(ng)
                for ng in self.cluster.network_groups)

    def get_admin_network_group(self):
        manager = self.get_network_manager()
        return manager.get_admin_network_group()


class NailgunReleaseAdapter(object):
    def __init__(self, release):
        self.release = release

    @classmethod
    def get_by_uid(cls, uid, fail_if_not_found=False):
        release = objects.Release.get_by_uid(
            uid, fail_if_not_found=fail_if_not_found)
        return release

    @property
    def is_deployable(self):
        return objects.Release.is_deployable(self.release)

    @property
    def environment_version(self):
        return self.release.environment_version

    def __cmp__(self, other):
        if isinstance(other, NailgunReleaseAdapter):
            other = other.release
        return self.release.__cmp__(other)


class NailgunNetworkManager(object):
    def __init__(self, cluster, net_manager):
        self.cluster = cluster
        self.net_manager = net_manager

    def update(self, network_configuration):
        self.net_manager.update(self.cluster, network_configuration)

    def get_assigned_vips(self):
        return self.net_manager.get_assigned_vips(self.cluster)

    def assign_vips_for_net_groups(self):
        return self.net_manager.assign_vips_for_net_groups(self.cluster)

    def assign_given_vips_for_net_groups(self, vips):
        self.net_manager.assign_given_vips_for_net_groups(self.cluster, vips)

    def get_admin_network_group(self, node_id=None):
        ng = self.net_manager.get_admin_network_group(node_id)
        return NailgunNetworkGroupAdapter(ng)

    def set_node_netgroups_ids(self, node, mapping):
        return self.net_manager.set_node_netgroups_ids(node.node, mapping)

    def set_nic_assignment_netgroups_ids(self, node, mapping):
        return self.net_manager.set_nic_assignment_netgroups_ids(
            node.node, mapping)

    def set_bond_assignment_netgroups_ids(self, node, mapping):
        return self.net_manager.set_bond_assignment_netgroups_ids(
            node.node, mapping)


class NailgunNodeAdapter(object):

    def __new__(cls, node=None):
        if not node:
            return None
        return super(NailgunNodeAdapter, cls).__new__(cls, node)

    def __init__(self, node):
        self.node = node

    @property
    def id(self):
        return self.node.id

    @property
    def cluster_id(self):
        return self.node.cluster_id

    @property
    def hostname(self):
        return self.node.hostname

    @hostname.setter
    def hostname(self, hostname):
        self.node.hostname = hostname

    @property
    def status(self):
        return self.node.status

    @property
    def error_type(self):
        return self.node.error_type

    @classmethod
    def get_by_uid(cls, node_id):
        return cls(objects.Node.get_by_uid(node_id))

    @property
    def roles(self):
        return self.node.roles

    def update_cluster_assignment(self, cluster):
        objects.Node.update_cluster_assignment(self.node, cluster)

    def add_pending_change(self, change):
        objects.Node.add_pending_change(self.node, change)


class NailgunNetworkGroupAdapter(object):

    def __init__(self, network_group):
        self.network_group = network_group

    @property
    def id(self):
        return self.network_group.id

    @property
    def name(self):
        return self.network_group.name
