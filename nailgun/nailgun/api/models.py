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
from datetime import datetime
from random import choice
import string
import uuid

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import Unicode
from sqlalchemy import UniqueConstraint
from sqlalchemy import ForeignKey, Enum, DateTime
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base
import web

from nailgun.api.fields import JSON
from nailgun.db import db
from nailgun.logger import logger
from nailgun.settings import settings
from nailgun.volumes.manager import VolumeManager


Base = declarative_base()


class NodeRoles(Base):
    __tablename__ = 'node_roles'
    id = Column(Integer, primary_key=True)
    role = Column(Integer, ForeignKey('roles.id', ondelete="CASCADE"))
    node = Column(Integer, ForeignKey('nodes.id'))


class PendingNodeRoles(Base):
    __tablename__ = 'pending_node_roles'
    id = Column(Integer, primary_key=True)
    role = Column(Integer, ForeignKey('roles.id', ondelete="CASCADE"))
    node = Column(Integer, ForeignKey('nodes.id'))


class Role(Base):
    __tablename__ = 'roles'
    id = Column(Integer, primary_key=True)
    release_id = Column(Integer, ForeignKey('releases.id', ondelete='CASCADE'))
    name = Column(String(50), nullable=False)


class GlobalParameters(Base):
    __tablename__ = 'global_parameters'
    id = Column(Integer, primary_key=True)
    parameters = Column(JSON, default={})


class Release(Base):
    __tablename__ = 'releases'
    __table_args__ = (
        UniqueConstraint('name', 'version'),
    )
    STATES = (
        'not_available',
        'downloading',
        'error',
        'available'
    )
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(100), nullable=False)
    version = Column(String(30), nullable=False)
    description = Column(Unicode)
    operating_system = Column(String(50), nullable=False)
    state = Column(Enum(*STATES, name='release_state'),
                   nullable=False,
                   default='not_available')
    networks_metadata = Column(JSON, default=[])
    attributes_metadata = Column(JSON, default={})
    volumes_metadata = Column(JSON, default={})
    modes_metadata = Column(JSON, default={})
    roles_metadata = Column(JSON, default={})
    role_list = relationship("Role", backref="release")
    clusters = relationship("Cluster", backref="release")

    @property
    def roles(self):
        return [role.name for role in self.role_list]

    @roles.setter
    def roles(self, roles):
        for role in roles:
            if role not in self.roles:
                self.role_list.append(Role(name=role, release=self))
        db().commit()


class ClusterChanges(Base):
    __tablename__ = 'cluster_changes'
    POSSIBLE_CHANGES = (
        'networks',
        'attributes',
        'disks'
    )
    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id'))
    node_id = Column(Integer, ForeignKey('nodes.id', ondelete='CASCADE'))
    name = Column(
        Enum(*POSSIBLE_CHANGES, name='possible_changes'),
        nullable=False
    )


class Cluster(Base):
    __tablename__ = 'clusters'
    MODES = ('multinode', 'ha_full', 'ha_compact')
    STATUSES = ('new', 'deployment', 'operational', 'error', 'remove')
    NET_MANAGERS = ('FlatDHCPManager', 'VlanManager')
    GROUPING = ('roles', 'hardware', 'both')
    # Neutron-related
    NET_PROVIDERS = ('nova_network', 'neutron')
    NET_L23_PROVIDERS = ('ovs',)
    NET_SEGMENT_TYPES = ('none', 'vlan', 'gre')
    id = Column(Integer, primary_key=True)
    mode = Column(
        Enum(*MODES, name='cluster_mode'),
        nullable=False,
        default='multinode'
    )
    status = Column(
        Enum(*STATUSES, name='cluster_status'),
        nullable=False,
        default='new'
    )
    net_provider = Column(
        Enum(*NET_PROVIDERS, name='net_provider'),
        nullable=False,
        default='nova_network'
    )
    net_l23_provider = Column(
        Enum(*NET_L23_PROVIDERS, name='net_l23_provider'),
        nullable=False,
        default='ovs'
    )
    net_segment_type = Column(
        Enum(*NET_SEGMENT_TYPES,
             name='net_segment_type'),
        nullable=False,
        default='vlan'
    )
    net_manager = Column(
        Enum(*NET_MANAGERS, name='cluster_net_manager'),
        nullable=False,
        default='FlatDHCPManager'
    )
    grouping = Column(
        Enum(*GROUPING, name='cluster_grouping'),
        nullable=False,
        default='roles'
    )
    name = Column(Unicode(50), unique=True, nullable=False)
    release_id = Column(Integer, ForeignKey('releases.id'), nullable=False)
    nodes = relationship("Node", backref="cluster", cascade="delete")
    tasks = relationship("Task", backref="cluster", cascade="delete")
    attributes = relationship("Attributes", uselist=False,
                              backref="cluster", cascade="delete")
    changes = relationship("ClusterChanges", backref="cluster",
                           cascade="delete")
    # We must keep all notifications even if cluster is removed.
    # It is because we want user to be able to see
    # the notification history so that is why we don't use
    # cascade="delete" in this relationship
    # During cluster deletion sqlalchemy engine will set null
    # into cluster foreign key column of notification entity
    notifications = relationship("Notification", backref="cluster")
    network_groups = relationship(
        "NetworkGroup",
        backref="cluster",
        cascade="delete",
        order_by="NetworkGroup.id"
    )
    dns_nameservers = Column(JSON, default=[
        "8.8.8.8",
        "8.8.4.4"
    ])
    replaced_deployment_info = Column(JSON, default={})
    replaced_provisioning_info = Column(JSON, default={})
    is_customized = Column(Boolean, default=False)

    def replace_provisioning_info(self, data):
        self.replaced_provisioning_info = data
        self.is_customized = True
        return self.replaced_provisioning_info

    def replace_deployment_info(self, data):
        self.replaced_deployment_info = data
        self.is_customized = True
        return self.replaced_deployment_info

    neutron_config = relationship("NeutronConfig",
                                  backref=backref("cluster"),
                                  uselist=False)

    @property
    def is_ha_mode(self):
        return self.mode in ('ha_full', 'ha_compact')

    def raise_if_attributes_locked(self):
        if self.status != "new" or any(
            map(
                lambda x: x.name == "deploy" and x.status == "running",
                self.tasks
            )
        ):
            error = web.forbidden()
            error.data = "Cluster attributes can't be changed " \
                         "after or in deploy."
            raise error

    @property
    def full_name(self):
        return '%s (id=%s, mode=%s)' % (self.name, self.id, self.mode)

    @classmethod
    def validate(cls, data):
        d = cls.validate_json(data)
        if d.get("name"):
            if db().query(Cluster).filter_by(
                name=d["name"]
            ).first():
                c = web.webapi.conflict
                c.message = "Environment with this name already exists"
                raise c()
        if d.get("release"):
            release = db().query(Release).get(d.get("release"))
            if not release:
                raise web.webapi.badrequest(message="Invalid release id")
        return d

    def add_pending_changes(self, changes_type, node_id=None):
        ex_chs = db().query(ClusterChanges).filter_by(
            cluster=self,
            name=changes_type
        )
        if not node_id:
            ex_chs = ex_chs.first()
        else:
            ex_chs = ex_chs.filter_by(node_id=node_id).first()
        # do nothing if changes with the same name already pending
        if ex_chs:
            return
        ch = ClusterChanges(
            cluster_id=self.id,
            name=changes_type
        )
        if node_id:
            ch.node_id = node_id
        db().add(ch)
        db().commit()

    def clear_pending_changes(self, node_id=None):
        chs = db().query(ClusterChanges).filter_by(
            cluster_id=self.id
        )
        if node_id:
            chs = chs.filter_by(node_id=node_id)
        map(db().delete, chs.all())
        db().commit()

    def prepare_for_deployment(self):
        from nailgun.network.manager import NetworkManager
        from nailgun.task.helpers import TaskHelper

        nodes = sorted(set(
            TaskHelper.nodes_to_deploy(self) +
            TaskHelper.nodes_in_provisioning(self)), key=lambda node: node.id)

        TaskHelper.update_slave_nodes_fqdn(nodes)

        nodes_ids = [n.id for n in nodes]
        netmanager = NetworkManager()
        if nodes_ids:
            netmanager.assign_ips(nodes_ids, 'management')
            netmanager.assign_ips(nodes_ids, 'public')
            netmanager.assign_ips(nodes_ids, 'storage')

            for node in nodes:
                netmanager.assign_admin_ips(
                    node.id, len(node.meta.get('interfaces', [])))

    def prepare_for_provisioning(self):
        from nailgun.network.manager import NetworkManager
        from nailgun.task.helpers import TaskHelper

        netmanager = NetworkManager()
        nodes = TaskHelper.nodes_to_provision(self)
        TaskHelper.update_slave_nodes_fqdn(nodes)
        for node in nodes:
            netmanager.assign_admin_ips(
                node.id, len(node.meta.get('interfaces', [])))


class Node(Base):
    __tablename__ = 'nodes'
    NODE_STATUSES = (
        'ready',
        'discover',
        'provisioning',
        'provisioned',
        'deploying',
        'error'
    )
    NODE_ERRORS = (
        'deploy',
        'provision',
        'deletion'
    )
    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id'))
    name = Column(Unicode(100))
    status = Column(
        Enum(*NODE_STATUSES, name='node_status'),
        nullable=False,
        default='discover'
    )
    meta = Column(JSON, default={})
    mac = Column(String(17), nullable=False, unique=True)
    ip = Column(String(15))
    fqdn = Column(String(255))
    manufacturer = Column(Unicode(50))
    platform_name = Column(String(150))
    progress = Column(Integer, default=0)
    os_platform = Column(String(150))
    pending_addition = Column(Boolean, default=False)
    pending_deletion = Column(Boolean, default=False)
    changes = relationship("ClusterChanges", backref="node")
    error_type = Column(Enum(*NODE_ERRORS, name='node_error_type'))
    error_msg = Column(String(255))
    timestamp = Column(DateTime, nullable=False)
    online = Column(Boolean, default=True)
    role_list = relationship("Role", secondary=NodeRoles.__table__)
    pending_role_list = relationship("Role",
                                     secondary=PendingNodeRoles.__table__)
    attributes = relationship("NodeAttributes",
                              backref=backref("node"),
                              uselist=False)
    interfaces = relationship("NodeNICInterface", backref="node",
                              cascade="delete")

    @property
    def offline(self):
        return not self.online

    @property
    def network_data(self):
        from nailgun.network.manager import NetworkManager
        netmanager = NetworkManager()
        return netmanager.get_node_networks(self.id)

    @property
    def volume_manager(self):
        return VolumeManager(self)

    @property
    def needs_reprovision(self):
        return self.status == 'error' and self.error_type == 'provision' and \
            not self.pending_deletion

    @property
    def needs_redeploy(self):
        return (self.status == 'error' or len(self.pending_roles)) and \
            not self.pending_deletion

    @property
    def needs_redeletion(self):
        return self.status == 'error' and self.error_type == 'deletion'

    @property
    def human_readable_name(self):
        return self.name or self.mac

    @property
    def full_name(self):
        return u'%s (id=%s, mac=%s)' % (self.name, self.id, self.mac)

    @property
    def roles(self):
        return [role.name for role in self.role_list]

    @roles.setter
    def roles(self, new_roles):
        self.role_list = map(lambda role: Role(name=role), new_roles)
        db().commit()

    @property
    def pending_roles(self):
        return [role.name for role in self.pending_role_list]

    @property
    def all_roles(self):
        """Returns all roles, self.roles and self.pending_roles."""
        return set(self.pending_roles + self.roles)

    @pending_roles.setter
    def pending_roles(self, new_roles):
        self.pending_role_list = map(
            lambda role: Role(name=role), new_roles)

        db().commit()

    @property
    def admin_interface(self):
        """Iterate over interfaces, if admin subnet include
        ip address of current interface then return this interface.

        :raises: errors.CanNotFindInterface
        """
        from nailgun.network.manager import NetworkManager
        network_manager = NetworkManager()

        for interface in self.interfaces:
            ip_addr = interface.ip_addr
            if network_manager.is_ip_belongs_to_admin_subnet(ip_addr):
                return interface

        logger.warning(u'Cannot find admin interface for node '
                       'return first interface: "%s"' %
                       self.full_name)
        return self.interfaces[0]

    def _check_interface_has_required_params(self, iface):
        return bool(iface.get('name') and iface.get('mac'))

    def _clean_iface(self, iface):
        # cleaning up unnecessary fields - set to None if bad
        for param in ["max_speed", "current_speed"]:
            val = iface.get(param)
            if not (isinstance(val, int) and val >= 0):
                val = None
            iface[param] = val
        return iface

    def update_meta(self, data):
        # helper for basic checking meta before updation
        result = []
        for iface in data["interfaces"]:
            if not self._check_interface_has_required_params(iface):
                logger.warning(
                    "Invalid interface data: {0}. "
                    "Interfaces are not updated.".format(iface)
                )
                data["interfaces"] = self.meta.get("interfaces")
                self.meta = data
                return
            result.append(self._clean_iface(iface))

        data["interfaces"] = result
        self.meta = data

    def create_meta(self, data):
        # helper for basic checking meta before creation
        result = []
        for iface in data["interfaces"]:
            if not self._check_interface_has_required_params(iface):
                logger.warning(
                    "Invalid interface data: {0}. "
                    "Skipping interface.".format(iface)
                )
                continue
            result.append(self._clean_iface(iface))

        data["interfaces"] = result
        self.meta = data


class NodeAttributes(Base):
    __tablename__ = 'node_attributes'
    id = Column(Integer, primary_key=True)
    node_id = Column(Integer, ForeignKey('nodes.id'))
    volumes = Column(JSON, default=[])
    interfaces = Column(JSON, default={})


class IPAddr(Base):
    __tablename__ = 'ip_addrs'
    id = Column(Integer, primary_key=True)
    network = Column(Integer, ForeignKey('networks.id', ondelete="CASCADE"))
    node = Column(Integer, ForeignKey('nodes.id', ondelete="CASCADE"))
    ip_addr = Column(String(25), nullable=False)

    network_data = relationship("Network")
    node_data = relationship("Node")


class IPAddrRange(Base):
    __tablename__ = 'ip_addr_ranges'
    id = Column(Integer, primary_key=True)
    network_group_id = Column(Integer, ForeignKey('network_groups.id'))
    first = Column(String(25), nullable=False)
    last = Column(String(25), nullable=False)


class Vlan(Base):
    __tablename__ = 'vlan'
    id = Column(Integer, primary_key=True)
    network = relationship("Network",
                           backref=backref("vlan"))


class Network(Base):
    __tablename__ = 'networks'
    id = Column(Integer, primary_key=True)
    # can be nullable only for fuelweb admin net
    release = Column(Integer, ForeignKey('releases.id'))
    name = Column(Unicode(100), nullable=False)
    vlan_id = Column(Integer, ForeignKey('vlan.id'))
    network_group_id = Column(Integer, ForeignKey('network_groups.id'))
    cidr = Column(String(25), nullable=False)
    gateway = Column(String(25))
    nodes = relationship(
        "Node",
        secondary=IPAddr.__table__,
        backref="networks")


class NetworkGroup(Base):
    __tablename__ = 'network_groups'
    NAMES = (
        # Node networks
        'fuelweb_admin',
        'storage',
        # internal in terms of fuel
        'management',
        'public',

        # VM networks
        'floating',
        # private in terms of fuel
        'fixed',
        'private'
    )

    id = Column(Integer, primary_key=True)
    name = Column(Enum(*NAMES, name='network_group_name'), nullable=False)
    # can be nullable only for fuelweb admin net
    release = Column(Integer, ForeignKey('releases.id'))
    # can be nullable only for fuelweb admin net
    cluster_id = Column(Integer, ForeignKey('clusters.id'))
    network_size = Column(Integer, default=256)
    amount = Column(Integer, default=1)
    vlan_start = Column(Integer)
    networks = relationship("Network", cascade="delete",
                            backref="network_group")
    cidr = Column(String(25))
    gateway = Column(String(25))

    netmask = Column(String(25), nullable=False)
    ip_ranges = relationship(
        "IPAddrRange",
        backref="network_group"
    )

    @classmethod
    def generate_vlan_ids_list(cls, ng):
        if ng["vlan_start"] is None:
            return []
        vlans = [
            i for i in xrange(
                int(ng["vlan_start"]),
                int(ng["vlan_start"]) + int(ng["amount"])
            )
        ]
        return vlans


class NetworkConfiguration(object):
    @classmethod
    def update(cls, cluster, network_configuration):
        from nailgun.network.manager import NetworkManager
        network_manager = NetworkManager()

        if 'net_manager' in network_configuration:
            setattr(
                cluster,
                'net_manager',
                network_configuration['net_manager']
            )

        if 'dns_nameservers' in network_configuration:
            setattr(
                cluster,
                'dns_nameservers',
                network_configuration['dns_nameservers']['nameservers']
            )

        if 'networks' in network_configuration:
            for ng in network_configuration['networks']:
                if ng['id'] == network_manager.get_admin_network_group_id():
                    continue

                ng_db = db().query(NetworkGroup).get(ng['id'])

                for key, value in ng.iteritems():
                    if key == "ip_ranges":
                        cls._set_ip_ranges(ng['id'], value)
                    else:
                        if key == 'cidr' and \
                                not ng['name'] in ('public', 'floating'):
                            network_manager.update_ranges_from_cidr(
                                ng_db, value)

                        setattr(ng_db, key, value)

                network_manager.create_networks(ng_db)
                ng_db.cluster.add_pending_changes('networks')

    @classmethod
    def _set_ip_ranges(cls, network_group_id, ip_ranges):
        # deleting old ip ranges
        db().query(IPAddrRange).filter_by(
            network_group_id=network_group_id).delete()

        for r in ip_ranges:
            new_ip_range = IPAddrRange(
                first=r[0],
                last=r[1],
                network_group_id=network_group_id)
            db().add(new_ip_range)
        db().commit()


class NeutronNetworkConfiguration(NetworkConfiguration):
    @classmethod
    def update(cls, cluster, network_configuration):
        from nailgun.network.neutron import NeutronManager
        network_manager = NeutronManager()
        if 'networks' in network_configuration:
            for ng in network_configuration['networks']:
                if ng['id'] == network_manager.get_admin_network_group_id():
                    continue

                ng_db = db().query(NetworkGroup).get(ng['id'])

                for key, value in ng.iteritems():
                    if key == "ip_ranges":
                        cls._set_ip_ranges(ng['id'], value)
                    else:
                        if key == 'cidr' and \
                                not ng['name'] in ('private',):
                            network_manager.update_ranges_from_cidr(
                                ng_db, value)

                        setattr(ng_db, key, value)

                if ng['name'] != 'private':
                    network_manager.create_networks(ng_db)
                ng_db.cluster.add_pending_changes('networks')

        if 'neutron_parameters' in network_configuration:
            for key, value in network_configuration['neutron_parameters'] \
                    .items():
                setattr(cluster.neutron_config, key, value)
            db().add(cluster.neutron_config)
            db().commit()


class NeutronConfig(Base):
    __tablename__ = 'neutron_configs'
    NET_SEGMENT_TYPES = ('vlan', 'gre')
    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id'))
    parameters = Column(JSON, default={})
    L2 = Column(JSON, default={})
    L3 = Column(JSON, default={})
    predefined_networks = Column(JSON, default={})

    segmentation_type = Column(
        Enum(*NET_SEGMENT_TYPES,
             name='segmentation_type'),
        nullable=False,
        default='vlan'
    )


class AttributesGenerators(object):
    @classmethod
    def password(cls, arg=None):
        try:
            length = int(arg)
        except Exception:
            length = 8
        chars = string.letters + string.digits
        return u''.join([choice(chars) for _ in xrange(length)])

    @classmethod
    def ip(cls, arg=None):
        if str(arg) in ("admin", "master"):
            return settings.MASTER_IP
        return "127.0.0.1"

    @classmethod
    def identical(cls, arg=None):
        return str(arg)


class Attributes(Base):
    __tablename__ = 'attributes'
    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id'))
    editable = Column(JSON)
    generated = Column(JSON)

    def generate_fields(self):
        self.generated = self.traverse(self.generated)
        db().add(self)
        db().commit()

    @classmethod
    def traverse(cls, cdict):
        new_dict = {}
        if cdict:
            for i, val in cdict.iteritems():
                if isinstance(val, (str, unicode, int, float)):
                    new_dict[i] = val
                elif isinstance(val, dict) and "generator" in val:
                    try:
                        generator = getattr(
                            AttributesGenerators,
                            val["generator"]
                        )
                    except AttributeError:
                        logger.error("Attribute error: %s" % val["generator"])
                        raise
                    else:
                        new_dict[i] = generator(val.get("generator_arg"))
                else:
                    new_dict[i] = cls.traverse(val)
        return new_dict

    def merged_attrs(self):
        return self._dict_merge(self.generated, self.editable)

    def merged_attrs_values(self):
        attrs = self.merged_attrs()
        for group_attrs in attrs.itervalues():
            for attr, value in group_attrs.iteritems():
                if isinstance(value, dict) and 'value' in value:
                    group_attrs[attr] = value['value']
        if 'common' in attrs:
            attrs.update(attrs.pop('common'))
        if 'additional_components' in attrs:
            for comp, enabled in attrs['additional_components'].iteritems():
                attrs.setdefault(comp, {}).update({
                    "enabled": enabled
                })
            attrs.pop('additional_components')
        return attrs

    def _dict_merge(self, a, b):
        '''recursively merges dict's. not just simple a['key'] = b['key'], if
        both a and bhave a key who's value is a dict then dict_merge is called
        on both values and the result stored in the returned dictionary.
        '''
        if not isinstance(b, dict):
            return b
        result = deepcopy(a)
        for k, v in b.iteritems():
            if k in result and isinstance(result[k], dict):
                    result[k] = self._dict_merge(result[k], v)
            else:
                result[k] = deepcopy(v)
        return result


class Task(Base):
    __tablename__ = 'tasks'
    TASK_STATUSES = (
        'ready',
        'running',
        'error'
    )
    TASK_NAMES = (
        'super',

        # cluster
        'deploy',
        'deployment',
        'provision',
        'node_deletion',
        'cluster_deletion',
        'check_before_deployment',

        # network
        'check_networks',
        'verify_networks',
        'check_dhcp',
        'verify_network_connectivity',

        # plugin
        'install_plugin',
        'update_plugin',
        'delete_plugin',

        # red hat
        'redhat_setup',
        'redhat_check_credentials',
        'redhat_check_licenses',
        'redhat_download_release',
        'redhat_update_cobbler_profile',

        # dump
        'dump',

        'capacity_log'
    )
    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id'))
    uuid = Column(String(36), nullable=False,
                  default=lambda: str(uuid.uuid4()))
    name = Column(
        Enum(*TASK_NAMES, name='task_name'),
        nullable=False,
        default='super'
    )
    message = Column(Text)
    status = Column(
        Enum(*TASK_STATUSES, name='task_status'),
        nullable=False,
        default='running'
    )
    progress = Column(Integer, default=0)
    cache = Column(JSON, default={})
    result = Column(JSON, default={})
    parent_id = Column(Integer, ForeignKey('tasks.id'))
    subtasks = relationship(
        "Task",
        backref=backref('parent', remote_side=[id])
    )
    notifications = relationship(
        "Notification",
        backref=backref('task', remote_side=[id])
    )
    # Task weight is used to calculate supertask progress
    # sum([t.progress * t.weight for t in supertask.subtasks]) /
    # sum([t.weight for t in supertask.subtasks])
    weight = Column(Float, default=1.0)

    def __repr__(self):
        return "<Task '{0}' {1} ({2}) {3}>".format(
            self.name,
            self.uuid,
            self.cluster_id,
            self.status
        )

    def create_subtask(self, name):
        if not name:
            raise ValueError("Subtask name not specified")

        task = Task(name=name, cluster=self.cluster)

        self.subtasks.append(task)
        db().commit()
        return task


class Notification(Base):
    __tablename__ = 'notifications'

    NOTIFICATION_STATUSES = (
        'read',
        'unread',
    )

    NOTIFICATION_TOPICS = (
        'discover',
        'done',
        'error',
        'warning',
    )

    id = Column(Integer, primary_key=True)
    cluster_id = Column(
        Integer,
        ForeignKey('clusters.id', ondelete='SET NULL')
    )
    node_id = Column(Integer, ForeignKey('nodes.id', ondelete='SET NULL'))
    task_id = Column(Integer, ForeignKey('tasks.id', ondelete='SET NULL'))
    topic = Column(
        Enum(*NOTIFICATION_TOPICS, name='notif_topic'),
        nullable=False
    )
    message = Column(Text)
    status = Column(
        Enum(*NOTIFICATION_STATUSES, name='notif_status'),
        nullable=False,
        default='unread'
    )
    datetime = Column(DateTime, nullable=False)


class L2Topology(Base):
    __tablename__ = 'l2_topologies'
    id = Column(Integer, primary_key=True)
    network_id = Column(
        Integer,
        ForeignKey('network_groups.id', ondelete="CASCADE"),
        nullable=False
    )


class L2Connection(Base):
    __tablename__ = 'l2_connections'
    id = Column(Integer, primary_key=True)
    topology_id = Column(
        Integer,
        ForeignKey('l2_topologies.id', ondelete="CASCADE"),
        nullable=False
    )
    interface_id = Column(
        Integer,
        # If interface is removed we should somehow remove
        # all L2Topologes which include this interface.
        ForeignKey('node_nic_interfaces.id', ondelete="CASCADE"),
        nullable=False
    )


class AllowedNetworks(Base):
    __tablename__ = 'allowed_networks'
    id = Column(Integer, primary_key=True)
    network_id = Column(
        Integer,
        ForeignKey('network_groups.id', ondelete="CASCADE"),
        nullable=False
    )
    interface_id = Column(
        Integer,
        ForeignKey('node_nic_interfaces.id', ondelete="CASCADE"),
        nullable=False
    )


class NetworkAssignment(Base):
    __tablename__ = 'net_assignments'
    id = Column(Integer, primary_key=True)
    network_id = Column(
        Integer,
        ForeignKey('network_groups.id', ondelete="CASCADE"),
        nullable=False
    )
    interface_id = Column(
        Integer,
        ForeignKey('node_nic_interfaces.id', ondelete="CASCADE"),
        nullable=False
    )


class NodeNICInterface(Base):
    __tablename__ = 'node_nic_interfaces'
    id = Column(Integer, primary_key=True)
    node_id = Column(
        Integer,
        ForeignKey('nodes.id', ondelete="CASCADE"),
        nullable=False)
    name = Column(String(128), nullable=False)
    mac = Column(String(32), nullable=False)
    max_speed = Column(Integer)
    current_speed = Column(Integer)
    allowed_networks = relationship(
        "NetworkGroup",
        secondary=AllowedNetworks.__table__,
        order_by="NetworkGroup.id")
    assigned_networks = relationship(
        "NetworkGroup",
        secondary=NetworkAssignment.__table__,
        order_by="NetworkGroup.id")
    ip_addr = Column(String(25))
    netmask = Column(String(25))


class Plugin(Base):
    __tablename__ = 'plugins'
    TYPES = ('nailgun', 'fuel')

    id = Column(Integer, primary_key=True)
    type = Column(Enum(*TYPES, name='plugin_type'), nullable=False)
    name = Column(String(128), nullable=False, unique=True)
    state = Column(String(128), nullable=False, default='registered')
    version = Column(String(128), nullable=False)


class RedHatAccount(Base):
    __tablename__ = 'red_hat_accounts'
    LICENSE_TYPES = ('rhsm', 'rhn')

    id = Column(Integer, primary_key=True)
    username = Column(String(100), nullable=False)
    password = Column(String(100), nullable=False)
    license_type = Column(Enum(*LICENSE_TYPES, name='license_type'),
                          nullable=False)
    satellite = Column(String(250))
    activation_key = Column(String(300))


class CapacityLog(Base):
    __tablename__ = 'capacity_log'

    id = Column(Integer, primary_key=True)
    report = Column(JSON)
    datetime = Column(DateTime, default=datetime.now())
