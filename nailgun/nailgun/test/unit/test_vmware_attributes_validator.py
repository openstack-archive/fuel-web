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
from mock import patch

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
                "api": False,
                "vmware_attributes": {
                    "editable": {"value": vmware_attributes}}
            },
            nodes_kwargs=[{
                "hostname": "controller-node",
                "status": consts.NODE_STATUSES.ready
            }, {
                "hostname": "node-1",
                "name": "Node 1",
                "roles": ["compute-vmware"],
                "status": consts.NODE_STATUSES.ready
            }]
        )
        self.cluster = self.env.clusters[0]

    def test_change_exist_nova_compute(self):
        attributes = self.cluster.vmware_attributes
        new_attributes = deepcopy(attributes.editable["value"])
        new_attributes["availability_zones"][0]["nova_computes"][0] = {
            "datastore_regex": ".*",
            "vsphere_cluster": "ClusterXX",
            "target_node": {
                "current": {
                    "id": "node-1",
                    "label": "node-1"
                },
            },
            "service_name": "ns1"
        }
        msg = ("Parameter 'vsphere_cluster' of nova compute instance of "
               "vSphere cluster 'Cluster1' couldn't be changed")
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            VmwareAttributesValidator._validate_nova_computes(
                {"editable": {"value": new_attributes}},
                attributes)

    def test_duplicate_values_for_nova_computes(self):
        attributes = self.cluster.vmware_attributes
        exist_nova_computes = objects.VmwareAttributes.get_nova_computes_attrs(
            attributes.editable)
        for attr in ("vsphere_cluster", "target_node", "service_name"):
            nova_computes = deepcopy(exist_nova_computes)
            duplicate_value = exist_nova_computes[0][attr]
            new_nova_compute = {
                "datastore_regex": ".*",
                "vsphere_cluster": "ClusterXX",
                "target_node": {
                    "current": {
                        "id": "node-X",
                        "label": "node-X"
                    },
                },
                "service_name": "nsXX"
            }
            new_nova_compute.update({attr: duplicate_value})
            nova_computes.append(new_nova_compute)

            duplicate_value = duplicate_value if attr != "target_node" \
                else duplicate_value["current"]["id"]
            msg = "Duplicate value '{0}' for attribute '{1}' is not allowed".\
                format(duplicate_value, attr)
            with self.assertRaisesRegexp(errors.InvalidData, msg):
                VmwareAttributesValidator._validate_nova_computes(
                    {
                        "editable": {
                            "value": {
                                "availability_zones": [{
                                    "nova_computes": nova_computes
                                }]
                            }
                        }
                    },
                    attributes
                )

    def test_empty_values_for_nova_computes(self):
        attributes = self.cluster.vmware_attributes
        nova_computes = objects.VmwareAttributes.get_nova_computes_attrs(
            attributes.editable)
        nova_computes[0]["vsphere_cluster"] = ""
        msg = "Empty value for attribute 'vsphere_cluster' is not allowed"
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            VmwareAttributesValidator._validate_nova_computes(
                {"editable": attributes.editable},
                attributes
            )

    def test_nova_compute_setting_validate(self):
        new_compute_vmware_node = self.env.create_node(
            hostname="node-2",
            name="Node 2",
            pending_roles=["compute-vmware"],
            pending_addition=True,
            cluster_id=self.cluster.id
        )
        self.env.create_node(
            hostname="node-3",
            name="Node 3",
            pending_roles=["compute-vmware"],
            pending_deletion=True,
            cluster_id=self.cluster.id
        )
        attributes = self.cluster.vmware_attributes
        new_attributes = deepcopy(attributes.editable)
        new_attributes.pop("metadata", None)
        new_nova_computes = objects.VmwareAttributes.get_nova_computes_attrs(
            new_attributes)
        new_nova_computes.extend([{
            "datastore_regex": ".*",
            "vsphere_cluster": "Cluster2",
            "target_node": {
                "current": {
                    "id": new_compute_vmware_node.hostname,
                    "label": new_compute_vmware_node.name
                }
            },
            "service_name": "ns2"
        }])
        self.assertNotRaises(errors.InvalidData,
                             VmwareAttributesValidator._validate_nova_computes,
                             {"editable": new_attributes},
                             attributes)

    @patch("nailgun.db.sqlalchemy.models.Cluster.is_locked", return_value=True)
    def test_change_controllers_nova_compute_setting(self, lock_mock):
        attributes = self.cluster.vmware_attributes
        new_attributes = deepcopy(attributes.editable)
        new_attributes.pop("metadata", None)
        new_nova_computes = objects.VmwareAttributes.get_nova_computes_attrs(
            new_attributes)
        changed_vsphera_cluster = None
        for nc in new_nova_computes:
            if objects.VmwareAttributes.get_compute_target_id(nc) == \
                    "controllers":
                nc["service_name"] = "new_service_name"
                changed_vsphera_cluster = nc
                break
        msg = ("Parameter '{0}' of nova compute instance with vSphere cluster "
               "name '{1}' couldn't be changed").format(
                   "service_name",
                   changed_vsphera_cluster["vsphere_cluster"])
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            VmwareAttributesValidator._validate_nova_computes(
                {"editable": new_attributes}, attributes)

    @patch("nailgun.db.sqlalchemy.models.Cluster.is_locked",
           return_value=True)
    def test_add_controllers_nova_compute_setting(self, lock_mock):
        attributes = self.cluster.vmware_attributes
        new_attributes = deepcopy(attributes.editable)
        new_attributes.pop("metadata", None)
        new_nova_computes = objects.VmwareAttributes.get_nova_computes_attrs(
            new_attributes)
        new_nova_computes.extend([{
            "datastore_regex": ".*",
            "vsphere_cluster": "Cluster20",
            "target_node": {
                "current": {
                    "id": "controllers",
                    "label": "controllers"
                }
            },
            "service_name": "ns20"
        }, {
            "datastore_regex": ".*",
            "vsphere_cluster": "Cluster30",
            "target_node": {
                "current": {
                    "id": "controllers",
                    "label": "controllers"
                }
            },
            "service_name": "ns30"
        }])
        msg = ("Nova compute instances with target 'controllers' couldn't be "
               "added to operational environment. Check nova compute "
               "instances with the following vSphere cluster names: {0}".
               format(", ".join(sorted(["Cluster30", "Cluster20"]))))
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            VmwareAttributesValidator._validate_nova_computes(
                {"editable": new_attributes}, attributes)

    @patch("nailgun.db.sqlalchemy.models.Cluster.is_locked",
           return_value=True)
    def test_remove_controllers_nova_compute_setting(self, lock_mock):
        attributes = self.cluster.vmware_attributes
        new_attributes = deepcopy(attributes.editable)
        new_attributes.pop("metadata", None)
        new_nova_computes = objects.VmwareAttributes.get_nova_computes_attrs(
            new_attributes)
        new_nova_computes = [
            nc for nc in new_nova_computes if
            objects.VmwareAttributes.get_compute_target_id != "controllers"
        ]
        msg = ("The following nova compute instance with target "
               "'controllers' couldn't be deleted from operational "
               "environment: nova compute with vSphere cluster name "
               "'{0}' ".format("Cluster0"))
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            VmwareAttributesValidator._validate_nova_computes(
                {"editable": {"value": new_attributes}}, attributes)

    def test_update_non_editable_attributes(self):
        metadata = [
            {
                "name": "foo",
                "label": "foo",
                "fields": [{
                    "name": "foo_field_name",
                    "label": "foo_field_name",
                }]
            }, {
                "name": "availability_zones",
                "label": "availability_zones",
                "fields": [{
                    "name": "az_name",
                    "label": "az_name",
                }, {
                    "name": "nova_computes",
                    "type": "array",
                    "fields": [{
                        "name": "vsphere_cluster",
                        "label": "vsphere_cluster",
                    }, {
                        "name": "target_node",
                        "label": "target_node",
                    }]
                }, {
                    "name": "vcenter_host",
                    "label": "vcenter_host",
                }]
            }
        ]
        db_attributes_value = {
            "availability_zones": [{
                "az_name": "az_1",
                "vcenter_host": "127.0.0.1",
                "nova_computes": [{
                    "vsphere_cluster": "Cluster1",
                    "target_node": {
                        "current": {"id": "node-1"}
                    }
                }]
            }],
            "foo": {
                "foo_field_name": "foo_field_value"
            }
        }
        instance = objects.VmwareAttributes.create(
            {"editable": {"metadata": metadata, "value": db_attributes_value}}
        )

        new_attributes = deepcopy(db_attributes_value)
        new_attributes["foo"] = ["foo_field_name"]
        msg = "Value type of 'foo' attribute couldn't be changed."
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            VmwareAttributesValidator._validate_updated_attributes(
                {"editable": {"value": new_attributes}},
                instance)

        new_attributes = deepcopy(db_attributes_value)
        new_attributes["availability_zones"].append({
            "az_name": "az_2",
            "vcenter_host": "127.0.0.1",
            "nova_computes": []
        })
        msg = "Value of 'availability_zones' attribute couldn't be changed."
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            VmwareAttributesValidator._validate_updated_attributes(
                {"editable": {"value": new_attributes}}, instance)

        new_attributes = deepcopy(db_attributes_value)
        new_attributes["availability_zones"][0]["nova_computes"][0].update(
            {"target_node": {"current": {"id": "node-2"}}}
        )
        msg = "Value of 'target_node' attribute couldn't be changed."
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            VmwareAttributesValidator._validate_updated_attributes(
                {"editable": {"value": new_attributes}}, instance)

    def test_update_editable_attributes(self):
        metadata = [
            {
                "name": "foo",
                "label": "foo",
                "editable_for_deployed": True,
                "fields": [{
                    "name": "foo_field_name",
                    "label": "foo_field_name",
                }]
            }, {
                "name": "availability_zones",
                "label": "availability_zones",
                "fields": [{
                    "name": "az_name",
                    "label": "az_name",
                }, {
                    "name": "nova_computes",
                    "editable_for_deployed": True,
                    "type": "array",
                    "fields": [{
                        "name": "vsphere_cluster",
                        "label": "vsphere_cluster",
                    }, {
                        "name": "target_node",
                        "label": "target_node",
                    }]
                }, {
                    "name": "vcenter_host",
                    "label": "vcenter_host",
                }]
            }
        ]
        db_attributes_value = {
            "availability_zones": [{
                "az_name": "az_1",
                "vcenter_host": "127.0.0.1",
                "nova_computes": [{
                    "vsphere_cluster": "Cluster1",
                    "target_node": {
                        "current": {"id": "node-1"}
                    }
                }]
            }],
            "foo": {
                "foo_field_name": "foo_field_value"
            }
        }
        instance = objects.VmwareAttributes.create(
            {"editable": {"metadata": metadata, "value": db_attributes_value}}
        )

        new_attributes = deepcopy(db_attributes_value)
        new_attributes["foo"]["foo_field_name"] = 1
        new_attributes["availability_zones"][0]["nova_computes"][0].update(
            {"target_node": {"current": {"id": "node-2"}}}
        )
        new_attributes["availability_zones"][0]["nova_computes"].append({
            "vsphere_cluster": "Cluster2",
            "target_node": {
                "current": {"id": "node-2"}
            }
        })
        self.assertNotRaises(
            errors.InvalidData,
            VmwareAttributesValidator._validate_updated_attributes,
            {"editable": {"value": new_attributes}},
            instance)
