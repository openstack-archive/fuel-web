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


from nailgun.db import db
from nailgun.db.sqlalchemy.models import Node
from nailgun.network.manager import NetworkManager


class TopoChecker(object):
    """This is POC and isn't in use now.
    """
    @classmethod
    def _is_assignment_allowed_for_node(cls, node):
        # This test is useless now
        db_node = db().query(Node).filter_by(id=node['id']).first()
        interfaces = node['interfaces']
        db_interfaces = db_node.interfaces
        for iface in interfaces:
            db_iface = filter(
                lambda i: i.id == iface['id'],
                db_interfaces
            )
            db_iface = db_iface[0]
            allowed_network_ids = \
                [n.id
                 for n in node.cluster.network_groups +
                 [NetworkManager.get_admin_network_group()]]
            for net in iface['assigned_networks']:
                if net['id'] not in allowed_network_ids:
                    return False
        return True

    @classmethod
    def is_assignment_allowed(cls, data):
        for node in data:
            if not cls._is_assignment_allowed_for_node(node):
                return False
        return True

    @classmethod
    def resolve_topo_conflicts(cls, data):
        raise NotImplementedError("Will be implemented later")
