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

from copy import deepcopy
from oslo_serialization import jsonutils

from nailgun.api.v1.validators.cluster import VmwareAttributesValidator
from nailgun import consts
from nailgun.errors import errors
from nailgun import objects
from nailgun.test.base import BaseTestCase


class TestAttributesValidator(BaseTestCase):
    def setUp(self):
        super(TestAttributesValidator, self).setUp()
        vmware_attributes = {
            "availability_zones": [{
                "vcenter_username": "admin",
                "az_name": "vcenter",
                "vcenter_password": "pass",
                "vcenter_host": "172.16.0.254",
                "nova_computes": [
                    {
                        "datastore_regex": ".*",
                        "vsphere_cluster": "Cluster1",
                        "target_node": {
                            "current": {
                                "id": "node-1",
                                "label": "node-1"
                            }
                        },
                        "service_name": "ns1"
                    },
                    {
                        "datastore_regex": ".*",
                        "vsphere_cluster": "Cluster0",
                        "target_node": {
                            "current": {
                                "id": "controllers",
                                "label": "controllers"
                            }
                        },
                        "service_name": "ns0"
                    }
                ]}
            ]
        }
        self.env.create(
            cluster_kwargs={
                'api': False,
                'vmware_attributes': {
                    'editable': {'value': vmware_attributes}}
            },
            nodes_kwargs=[{
                'status': consts.NODE_STATUSES.ready,
                'hostname': 'controller-node'
            }, {
                'hostname': 'node-1',
                'name': 'Node 1',
                'roles': ['compute-vmware'],
                'status': 'ready'
            }]
        )
        self.cluster = self.env.clusters[0]

    def test_change_exist_nova_compute(self):
        attributes = self.cluster.vmware_attributes
        new_attributes = deepcopy(attributes.editable['value'])
        new_attributes['availability_zones'][0]['nova_computes'][0] = {
            "datastore_regex": ".*",
            "vsphere_cluster": "ClusterXX",
            "target_node": {
                "current": {
                    "id": "node-1",
                    "label": "node-1"
                },
            },
            "service_name": "nsXX"
        }
        msg = "The nova compute instance with vSphere cluster " \
              "name 'Cluster1' couldn't be changed"
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            VmwareAttributesValidator.validate(
                jsonutils.dumps({
                    'editable': {'value': new_attributes}}),
                attributes)

    def test_new_compute_vmware_node_not_in_settings(self):
        new_compute_vmware_node = self.env.create_node(
            hostname='node-3',
            name='Node 3',
            pending_roles=['compute-vmware'],
            pending_addition=True,
            cluster_id=self.cluster.id
        )
        attributes = self.cluster.vmware_attributes
        msg = "The following compute-vmware nodes are not assigned to any " \
              "vCenter cluster: {0}".format(new_compute_vmware_node.name)
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            VmwareAttributesValidator.validate(
                jsonutils.dumps(attributes), attributes)

    def test_deletion_compute_vmware_node_in_settings(self):
        compute_vmware_node = [n for n in self.cluster.nodes
                               if 'compute-vmware' in n.roles][0]
        objects.Node.update(compute_vmware_node, {'pending_deletion': True})
        attributes = self.cluster.vmware_attributes
        msg = "The following node prepared for deletion and couldn't be " \
              "assigned to any vCenter cluster: {0}".format(
                  compute_vmware_node.name)
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            VmwareAttributesValidator.validate(
                jsonutils.dumps(attributes), attributes)

    def test_non_cluster_node_in_settings(self):
        attributes = self.cluster.vmware_attributes
        attributes.editable.get('value').get('availability_zones')[0].get(
            'nova_computes').extend([{
                "datastore_regex": ".*",
                "vsphere_cluster": "ClusterXX",
                "target_node": {
                    "current": {
                        "id": "node-X",
                        "label": "node-X"
                    },
                },
                "service_name": "nsXX"
            }, {
                "datastore_regex": ".*",
                "vsphere_cluster": "ClusterYY",
                "target_node": {
                    "current": {
                        "id": "node-Y",
                        "label": "node-Y"
                    },
                },
                "service_name": "nsYY"
            }])
        objects.Cluster.update_vmware_attributes(self.cluster, attributes)
        msg = "The following nodes couldn't be assigned to any vCenter " \
              "cluster: \[u'node-X', u'node-Y'\]"
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            VmwareAttributesValidator.validate(
                jsonutils.dumps(attributes), attributes)

    def test_setting_validate(self):
        new_compute_vmware_node = self.env.create_node(
            hostname='node-2',
            name='Node 2',
            pending_roles=['compute-vmware'],
            pending_addition=True,
            cluster_id=self.cluster.id
        )
        self.env.create_node(
            hostname='node-3',
            name='Node 3',
            pending_roles=['compute-vmware'],
            pending_deletion=True,
            cluster_id=self.cluster.id
        )
        attributes = self.cluster.vmware_attributes
        new_attributes = deepcopy(attributes.editable.get('value'))
        new_attributes['availability_zones'][0]['nova_computes'].append({
            "datastore_regex": ".*",
            "vsphere_cluster": "Cluster2",
            "target_node": {
                "current": {
                    "id": new_compute_vmware_node.hostname,
                    "label": new_compute_vmware_node.name
                }
            },
            "service_name": "ns2"
        })
        self.assertNotRaises(errors.InvalidData,
                             VmwareAttributesValidator.validate,
                             jsonutils.dumps({
                                 'editable': {'value': new_attributes}}),
                             attributes)
