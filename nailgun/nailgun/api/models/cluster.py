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
from random import choice
import string

import web

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Unicode
from sqlalchemy.orm import relationship, backref

from nailgun.api.models.base import Base
from nailgun.api.models.fields import JSON
from nailgun.api.models.release import Release
from nailgun.db import db
from nailgun.logger import logger
from nailgun.settings import settings


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
    nodes = relationship(
        "Node", backref="cluster", cascade="delete", order_by='Node.id')
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

    @property
    def full_name(self):
        return '%s (id=%s, mode=%s)' % (self.name, self.id, self.mode)

    @property
    def are_attributes_locked(self):
        return self.status != "new" or any(
            map(
                lambda x: x.name == "deploy" and x.status == "running",
                self.tasks
            )
        )

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

    @property
    def network_manager(self):
        if self.net_provider == 'neutron':
            from nailgun.network.neutron import NeutronManager
            return NeutronManager
        else:
            from nailgun.network.manager import NetworkManager
            return NetworkManager


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
