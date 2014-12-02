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

from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema.disks \
    import disks_simple_format_schema
from nailgun.api.v1.validators.json_schema import node_schema

from nailgun import objects

from nailgun.db import db
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import NodeNICInterface
from nailgun.errors import errors


class MetaInterfacesValidator(BasicValidator):
    @classmethod
    def _validate_data(cls, interfaces):
        if not isinstance(interfaces, list):
            raise errors.InvalidInterfacesInfo(
                "Meta.interfaces should be list",
                log_message=True
            )

        return interfaces

    @classmethod
    def validate_create(cls, interfaces):
        interfaces = cls._validate_data(interfaces)

        def filter_valid_nic(nic):
            for key in ('mac', 'name'):
                if key not in nic or not isinstance(nic[key], basestring)\
                        or not nic[key]:
                    return False
            return True

        return filter(filter_valid_nic, interfaces)

    @classmethod
    def validate_update(cls, interfaces):
        interfaces = cls._validate_data(interfaces)

        for nic in interfaces:
            if not isinstance(nic, dict):
                raise errors.InvalidInterfacesInfo(
                    "Interface in meta.interfaces must be dict",
                    log_message=True
                )

        return interfaces


class MetaValidator(BasicValidator):
    @classmethod
    def _validate_data(cls, meta):
        if not isinstance(meta, dict):
            raise errors.InvalidMetadata(
                "Invalid data: 'meta' should be dict",
                log_message=True
            )

    @classmethod
    def validate_create(cls, meta):
        cls._validate_data(meta)
        if 'interfaces' in meta:
            meta['interfaces'] = MetaInterfacesValidator.validate_create(
                meta['interfaces']
            )
        else:
            raise errors.InvalidInterfacesInfo(
                "Failed to discover node: "
                "invalid interfaces info",
                log_message=True
            )
        return meta

    @classmethod
    def validate_update(cls, meta):
        cls._validate_data(meta)
        if 'interfaces' in meta:
            meta['interfaces'] = MetaInterfacesValidator.validate_update(
                meta['interfaces']
            )
        return meta


class NodeValidator(BasicValidator):

    single_schema = node_schema.single_schema

    @classmethod
    def validate(cls, data):
        # TODO(enchantner): rewrite validators to use Node object
        data = cls.validate_json(data)

        if data.get("status", "") != "discover":
            raise errors.NotAllowed(
                "Only bootstrap nodes are allowed to be registered."
            )

        if 'mac' not in data:
            raise errors.InvalidData(
                "No mac address specified",
                log_message=True
            )

        if cls.does_node_exist_in_db(data):
            raise errors.AlreadyExists(
                "Node with mac {0} already "
                "exists - doing nothing".format(data["mac"]),
                log_level="info"
            )

        if cls.validate_existent_node_mac_create(data):
            raise errors.AlreadyExists(
                "Node with mac {0} already "
                "exists - doing nothing".format(data["mac"]),
                log_level="info"
            )

        if 'meta' in data:
            MetaValidator.validate_create(data['meta'])

        return data

    @classmethod
    def does_node_exist_in_db(cls, data):
        mac = data['mac'].lower()
        q = db().query(Node)

        if q.filter(Node.mac == mac).first() or \
            q.join(NodeNICInterface, Node.nic_interfaces).filter(
                NodeNICInterface.mac == mac).first():
            return True
        return False

    @classmethod
    def _validate_existent_node(cls, data, validate_method):
        if 'meta' in data:
            data['meta'] = validate_method(data['meta'])
            if 'interfaces' in data['meta']:
                existent_node = db().query(Node).\
                    join(NodeNICInterface, Node.nic_interfaces).\
                    filter(NodeNICInterface.mac.in_(
                        [n['mac'].lower() for n in data['meta']['interfaces']]
                    )).first()
                return existent_node

    @classmethod
    def validate_existent_node_mac_create(cls, data):
        return cls._validate_existent_node(
            data,
            MetaValidator.validate_create)

    @classmethod
    def validate_existent_node_mac_update(cls, data):
        return cls._validate_existent_node(
            data,
            MetaValidator.validate_update)

    @classmethod
    def validate_roles(cls, data, node):
        if 'roles' in data:
            if not isinstance(data['roles'], list) or \
                    any(not isinstance(role, (
                        str, unicode)) for role in data['roles']):
                raise errors.InvalidData(
                    "Role list must be list of strings",
                    log_message=True
                )

    @classmethod
    def validate_update(cls, data, instance=None):
        if isinstance(data, (str, unicode)):
            d = cls.validate_json(data)
        else:
            d = data
        cls.validate_schema(d, node_schema.single_schema)

        if not d.get("mac") and not d.get("id") and not instance:
            raise errors.InvalidData(
                "Neither MAC nor ID is specified",
                log_message=True
            )

        q = db().query(Node)
        if "mac" in d:
            existent_node = q.filter_by(mac=d["mac"].lower()).first() \
                or cls.validate_existent_node_mac_update(d)
            if not existent_node:
                raise errors.InvalidData(
                    "Invalid MAC is specified",
                    log_message=True
                )

        if "id" in d and d["id"]:
            existent_node = q.get(d["id"])
            if not existent_node:
                raise errors.InvalidData(
                    "Invalid ID specified",
                    log_message=True
                )

        if "roles" in d:
            if instance:
                node = instance
            else:
                node = objects.Node.get_by_mac_or_uid(
                    mac=d.get("mac"),
                    node_uid=d.get("id")
                )
            cls.validate_roles(d, node)

        if 'meta' in d:
            d['meta'] = MetaValidator.validate_update(d['meta'])
        return d

    @classmethod
    def validate_delete(cls, instance):
        pass

    @classmethod
    def validate_collection_update(cls, data):
        d = cls.validate_json(data)
        if not isinstance(d, list):
            raise errors.InvalidData(
                "Invalid json list",
                log_message=True
            )

        for nd in d:
            cls.validate_update(nd)
        return d


class NodeDisksValidator(BasicValidator):
    @classmethod
    def validate(cls, data, node=None):
        dict_data = cls.validate_json(data)
        cls.validate_schema(dict_data, disks_simple_format_schema)
        cls.at_least_one_disk_exists(dict_data)
        cls.sum_of_volumes_not_greater_than_disk_size(dict_data)
        # in case of Ubuntu we should allocate OS on one disk only
        # https://bugs.launchpad.net/fuel/+bug/1308592
        if node and node.cluster \
                and node.cluster.release.operating_system == "Ubuntu":
            cls.os_vg_single_disk(dict_data)
        return dict_data

    @classmethod
    def os_vg_single_disk(cls, data):
        os_vg_count = 0
        for disk in data:
            for vol in disk["volumes"]:
                if vol["name"] == "os" and vol["size"] > 0:
                    os_vg_count += 1
        if os_vg_count > 1:
            raise errors.InvalidData(
                u'Base system should be allocated on one disk only'
            )

    @classmethod
    def at_least_one_disk_exists(cls, data):
        if len(data) < 1:
            raise errors.InvalidData(u'Node seems not to have disks')

    @classmethod
    def sum_of_volumes_not_greater_than_disk_size(cls, data):
        for disk in data:
            volumes_size = sum([volume['size'] for volume in disk['volumes']])

            if volumes_size > disk['size']:
                raise errors.InvalidData(
                    u'Not enough free space on disk: %s' % disk)


class NodesFilterValidator(BasicValidator):

    @classmethod
    def validate(cls, nodes):
        """Used for filtering nodes
        :param nodes: list of ids in string representation.
                      Example: "1,99,3,4"

        :returns: list of integers
        """
        try:
            node_ids = set(map(int, nodes.split(',')))
        except ValueError:
            raise errors.InvalidData('Provided id is not integer')

        return node_ids
