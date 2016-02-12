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

from mock import patch

from nailgun.api.v1.validators.cluster import VmwareAttributesValidator
from nailgun import consts
from nailgun.db.sqlalchemy.models.mutable import MutableDict
from nailgun.errors import errors
from nailgun import objects
from nailgun.test.base import BaseTestCase


class TestAttributesValidator(BaseTestCase):
    def setUp(self):
        super(TestAttributesValidator, self).setUp()
        self.env.create(
            cluster_kwargs={
                "api": False,
                "vmware_attributes": {
                    "editable": self._get_value_vmware_attributes()
                }
            },
            nodes_kwargs=[{
                "hostname": "controller-node",
                "status": consts.NODE_STATUSES.ready
            }]
        )
        self.cluster = self.env.clusters[0]
        self.ready_compute_node = self.env.create_node(
            hostname="node-1",
            name="Node 1",
            roles=["compute-vmware"],
            status=consts.NODE_STATUSES.ready,
            cluster_id=self.cluster.id
        )

    def _get_target_id(self, nova_compute):
        return nova_compute["target_node"]["current"]["id"]

    def _get_default_nova_computes(self):
        return [
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
        ]

    def _get_value_vmware_attributes(self, nova_computes=None):
        return {
            "value": {
                "availability_zones": [{
                    "vcenter_username": "admin",
                    "az_name": "vcenter",
                    "vcenter_password": "pass",
                    "vcenter_host": "172.16.0.254",
                    "nova_computes":
                        nova_computes or self._get_default_nova_computes()
                }]
            }
        }

    def validate_nova_compute_raises_regexp(self, nova_computes, error_msg):
        with self.assertRaisesRegexp(errors.InvalidData, error_msg):
            VmwareAttributesValidator._validate_nova_computes(
                {"editable": self._get_value_vmware_attributes(nova_computes)},
                self.cluster.vmware_attributes
            )

    def test_change_exist_nova_compute(self):
        nova_computes = self._get_default_nova_computes()
        changed_attribute = 'vsphere_cluster'
        for nc in nova_computes:
            if self._get_target_id(nc) == self.ready_compute_node.hostname:
                nc[changed_attribute] = "ClusterXX"
                break

        self.validate_nova_compute_raises_regexp(
            nova_computes,
            "Parameter '{0}' of nova compute instance with target node '{1}' "
            "couldn't be changed".format(
                changed_attribute, self.ready_compute_node.name
            )
        )

    def test_delete_operational_nova_compute_node(self):
        nova_computes = [
            nc for nc in self._get_default_nova_computes() if
            self._get_target_id(nc) != self.ready_compute_node.hostname
        ]
        self.validate_nova_compute_raises_regexp(
            nova_computes,
            "The following compute-vmware node couldn't be deleted from "
            "vSphere cluster: {0}".format(self.ready_compute_node.name)
        )

    def test_duplicate_values_for_nova_computes(self):
        for attr in ("vsphere_cluster", "target_node", "service_name"):
            exist_nova_computes = self._get_default_nova_computes()
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
            exist_nova_computes.append(new_nova_compute)
            duplicate_value = duplicate_value if attr != "target_node" \
                else duplicate_value["current"]["id"]

            self.validate_nova_compute_raises_regexp(
                exist_nova_computes,
                "Duplicate value '{0}' for attribute '{1}' is not allowed".
                format(duplicate_value, attr)
            )

    def test_empty_values_for_nova_computes(self):
        nova_computes = self._get_default_nova_computes()
        nova_computes[0]["vsphere_cluster"] = ""
        self.validate_nova_compute_raises_regexp(
            nova_computes,
            "Empty value for attribute 'vsphere_cluster' is not allowed"
        )

    def test_nova_compute_setting_validate_pass(self):
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
            roles=["compute-vmware"],
            pending_deletion=True,
            cluster_id=self.cluster.id
        )
        attributes = self.cluster.vmware_attributes
        new_nova_computes = self._get_default_nova_computes()
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
                             {"editable": self._get_value_vmware_attributes(
                                 new_nova_computes)},
                             attributes)

    def test_change_controller_nova_computes_pass(self):
        cluster = self.env.create(
            cluster_kwargs={
                "api": False,
                "status": consts.CLUSTER_STATUSES.new,
                "vmware_attributes": {
                    "editable": self._get_value_vmware_attributes()
                }
            }
        )
        new_nova_computes = [nc for nc in self._get_default_nova_computes()
                             if self._get_target_id(nc) == "controllers"]
        new_nova_computes[0]["vsphere_cluster"] = "new vsphere name"
        new_nova_computes.append({
            "datastore_regex": ".*",
            "vsphere_cluster": "Cluster10",
            "target_node": {
                "current": {
                    "id": "controllers",
                    "label": "controllers"
                }
            },
            "service_name": "ns10"
        })
        self.assertNotRaises(errors.InvalidData,
                             VmwareAttributesValidator._validate_nova_computes,
                             {"editable": self._get_value_vmware_attributes(
                                 new_nova_computes)},
                             cluster.vmware_attributes)

    @patch("nailgun.db.sqlalchemy.models.Cluster.is_locked", return_value=True)
    def test_change_controllers_nova_compute_setting(self, lock_mock):
        new_nova_computes = self._get_default_nova_computes()
        changed_vsphere_cluster = None
        changed_attribute = "service_name"
        for nc in new_nova_computes:
            if self._get_target_id(nc) == "controllers":
                nc[changed_attribute] = "new_service_name"
                changed_vsphere_cluster = nc
                break

        self.validate_nova_compute_raises_regexp(
            new_nova_computes,
            "Parameter '{0}' of nova compute instance with vSphere cluster "
            "name '{1}' couldn't be changed".format(
                changed_attribute, changed_vsphere_cluster["vsphere_cluster"])
        )

    @patch("nailgun.db.sqlalchemy.models.Cluster.is_locked", return_value=True)
    def test_add_controllers_nova_compute_setting(self, lock_mock):
        new_nova_computes = self._get_default_nova_computes()
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
        self.validate_nova_compute_raises_regexp(
            new_nova_computes,
            "Nova compute instances with target 'controllers' couldn't be "
            "added to operational environment. Check nova compute instances "
            "with the following vSphere cluster names: {0}".format(
                ", ".join(sorted(["Cluster30", "Cluster20"]))
            )
        )

    @patch("nailgun.db.sqlalchemy.models.Cluster.is_locked", return_value=True)
    def test_remove_controllers_nova_compute_setting(self, lock_mock):
        new_nova_computes = [nc for nc in self._get_default_nova_computes()
                             if self._get_target_id(nc) != "controllers"]
        self.validate_nova_compute_raises_regexp(
            new_nova_computes,
            "Nova compute instance with target 'controllers' and vSphere "
            "cluster {0} couldn't be deleted from operational environment."
            .format("Cluster0")
        )

    def test_update_non_editable_attributes(self):
        metadata = [
            {
                "name": "foo",
                "label": "foo",
                "type": "object",
                "fields": [{
                    "name": "foo_field_name",
                    "label": "foo_field_name",
                }]
            }, {
                "name": "availability_zones",
                "label": "availability_zones",
                "type": "array",
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

        new_attributes = MutableDict(db_attributes_value)
        new_attributes["foo"] = ["foo_field_name"]
        msg = "Value type of 'foo_field_name' attribute couldn't be changed."
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            VmwareAttributesValidator._validate_updated_attributes(
                {"editable": {"value": new_attributes}},
                instance)

        new_attributes = MutableDict(db_attributes_value)
        new_attributes["foo"]["foo_field_name"] = "new_foo_field_value"
        msg = "Value of 'foo_field_name' attribute couldn't be changed."
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            VmwareAttributesValidator._validate_updated_attributes(
                {"editable": {"value": new_attributes}},
                instance)

        new_attributes = MutableDict(db_attributes_value)
        new_attributes["availability_zones"].append({
            "az_name": "az_2",
            "vcenter_host": "127.0.0.1",
            "nova_computes": []
        })
        msg = "Value of 'availability_zones' attribute couldn't be changed."
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            VmwareAttributesValidator._validate_updated_attributes(
                {"editable": {"value": new_attributes}}, instance)

        new_attributes = MutableDict(db_attributes_value)
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
                "type": "object",
                "editable_for_deployed": True,
                "fields": [{
                    "name": "foo_field_name",
                    "label": "foo_field_name",
                }]
            }, {
                "name": "availability_zones",
                "type": "array",
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

        new_attributes = MutableDict(db_attributes_value)
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
