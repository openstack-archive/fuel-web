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

import six

from nailgun.api.v1.validators import base
from nailgun.api.v1.validators.json_schema import base_types
from nailgun.api.v1.validators.json_schema import node_schema
from nailgun.api.v1.validators.orchestrator_graph import \
    TaskDeploymentValidator
from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import NodeNICInterface
from nailgun.errors import errors
from nailgun import objects
from nailgun import utils


class MetaInterfacesValidator(base.BasicValidator):
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
                if key not in nic or not isinstance(nic[key], six.string_types)\
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


class MetaValidator(base.BasicValidator):
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


class NodeValidator(base.BasicValidator):

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
                    any(not isinstance(role, six.string_types)
                        for role in data['roles']):
                raise errors.InvalidData(
                    "Role list must be list of strings",
                    log_message=True
                )

    @classmethod
    def validate_hostname(cls, hostname, instance):
        if hostname == instance.hostname:
            return

        if instance.status != consts.NODE_STATUSES.discover:
            raise errors.NotAllowed(
                "Node hostname may be changed only before provisioning."
            )

        if instance.cluster:
            cluster = instance.cluster
            public_ssl_endpoint = cluster.attributes.editable.get(
                'public_ssl', {}).get('hostname', {}).get('value', "")

            if public_ssl_endpoint in (
                hostname,
                objects.Node.generate_fqdn_by_hostname(hostname)
            ):
                raise errors.InvalidData(
                    "New hostname '{0}' conflicts with public TLS endpoint"
                    .format(hostname))
        if objects.Node.get_by_hostname(
                hostname,
                instance.cluster_id):
            raise errors.AlreadyExists(
                "Duplicate hostname '{0}'.".format(hostname)
            )

    @classmethod
    def validate_update(cls, data, instance=None):
        if isinstance(data, six.string_types):
            d = cls.validate_json(data)
        else:
            d = data
        cls.validate_schema(d, node_schema.single_schema)

        if not d.get("mac") and not d.get("id") and not instance:
            raise errors.InvalidData(
                "Neither MAC nor ID is specified",
                log_message=True
            )

        existent_node = None
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

        if not instance:
            instance = existent_node

        if d.get("hostname") is not None:
            cls.validate_hostname(d["hostname"], instance)

        if "roles" in d:
            cls.validate_roles(d, instance)

        if 'meta' in d:
            d['meta'] = MetaValidator.validate_update(d['meta'])

        if "group_id" in d:
            ng = objects.NodeGroup.get_by_uid(d["group_id"])
            if not ng:
                raise errors.InvalidData(
                    "Cannot assign node group (ID={0}) to node {1}. "
                    "The specified node group does not exist."
                    .format(d["group_id"], instance.id)
                )

            if not instance.cluster_id:
                raise errors.InvalidData(
                    "Cannot assign node group (ID={0}) to node {1}. "
                    "Node is not allocated to cluster."
                    .format(d["group_id"], instance.id)
                )

            if instance.cluster_id != ng.cluster_id:
                raise errors.InvalidData(
                    "Cannot assign node group (ID={0}) to node {1}. "
                    "Node belongs to other cluster than node group"
                    .format(d["group_id"], instance.id)
                )

        return d

    @classmethod
    def validate_delete(cls, data, instance):
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

    @classmethod
    def validate_collection_delete(cls, data):
        try:
            d = map(int, data.split(','))
        except ValueError:
            raise errors.InvalidData('Comma-separated number list expected',
                                     log_message=True)

        cls.validate_schema(d, base_types.IDS_ARRAY)

        return d


class NodesFilterValidator(base.BasicValidator):

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

    @classmethod
    def validate_placement(cls, nodes, cluster):
        """Validates that given nodes placed in given cluster

        :param nodes: list of objects.Node instances
        :param cluster: objects.Cluster instance
        """
        wrongly_placed_uids = []
        for node in nodes:
            if node.cluster_id != cluster.id:
                wrongly_placed_uids.append(node.uid)

        if wrongly_placed_uids:
            raise errors.InvalidData(
                'Nodes {} do not belong to cluster {}'.format(
                    ', '.join(wrongly_placed_uids), cluster.id))


class ProvisionSelectedNodesValidator(NodesFilterValidator):

    @classmethod
    def validate_provision(cls, data, cluster):
        """Check whether provision allowed or not for a given cluster

        :param data: raw json data, usually web.data()
        :param cluster: cluster instance
        :returns: loaded json or empty array
        """
        if cluster.release.state == consts.RELEASE_STATES.unavailable:
            raise errors.UnavailableRelease(
                "Release '{0} {1}' is unavailable!".format(
                    cluster.release.name, cluster.release.version))


class DeploySelectedNodesValidator(NodesFilterValidator):

    @classmethod
    def validate_nodes_to_deploy(cls, data, nodes, cluster_id):
        """Check if nodes scheduled for deployment are in proper state

        :param data: raw json data, usually web.data(). Is not used here
        and is needed for maintaining consistency of data validating logic
        :param nodes: list of node objects state of which to be checked
        :param cluster_id: id of the cluster for which operation is performed
        """

        # in some cases (e.g. user tries to deploy single controller node
        # via CLI or API for ha cluster) there may be situation when not
        # all nodes scheduled for deployment are provisioned, hence
        # here we check for such situation
        not_provisioned = []

        # it should not be possible to execute deployment tasks
        # on nodes that are marked for deletion
        pending_deletion = []
        for n in nodes:
            if any(
                [n.pending_addition,
                 n.needs_reprovision,
                 n.needs_redeletion,
                 n.status == consts.NODE_STATUSES.provisioning]
            ):
                not_provisioned.append(n.id)

            if n.pending_deletion:
                pending_deletion.append(n.id)

        if not (not_provisioned or pending_deletion):
            return

        err_msg = "Deployment operation cannot be started. "
        if not_provisioned:
            err_msg += (
                "Nodes with uids {0} are not provisioned yet. "
                .format(not_provisioned, cluster_id))
        if pending_deletion:
            err_msg += ("Nodes with uids {0} marked for deletion. "
                        "Please remove them and restart deployment."
                        .format(pending_deletion))

        raise errors.InvalidData(
            err_msg,
            log_message=True
        )


class NodeDeploymentValidator(TaskDeploymentValidator,
                              DeploySelectedNodesValidator):

    @classmethod
    def validate_deployment(cls, data, cluster):
        """Used to validate attributes used for validate_deployment_attributes

        :param data: raw json data, usually web.data()
        :returns: loaded json or empty array
        """
        data = cls.validate_json(data)

        if data:
            cls.validate_tasks(data, cluster)
        else:
            raise errors.InvalidData('Tasks list must be specified.')

        return data


class NodeAttributesValidator(base.BasicAttributesValidator):

    @classmethod
    def validate(cls, data, node):
        data = cls.validate_json(data)
        full_data = utils.dict_merge(objects.Node.get_attributes(node), data)
        attrs = cls.validate_attributes(full_data)

        cls._validate_cpu_pinning(node, attrs)

        return data

    @classmethod
    def _validate_cpu_pinning(cls, node, attrs):
        pining_info = objects.NodeAttributes.node_cpu_pinning_info(node, attrs)

        # check that we have at least one CPU for operating system
        total_cpus = int(node.meta.get('cpu', {}).get('total', 0))

        if total_cpus - pining_info['total_required_cpus'] < 1:
            raise errors.InvalidData(
                'Operating system requires at least one cpu '
                'that must not be pinned.'
            )
