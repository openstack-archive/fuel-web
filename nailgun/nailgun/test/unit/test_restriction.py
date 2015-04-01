# -*- coding: utf-8 -*-

#    Copyright 2014 Mirantis, Inc.
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
import yaml

from nailgun.errors import errors
from nailgun import objects
from nailgun.settings import settings
from nailgun.test import base
from nailgun.utils.restrictions import AttributesRestriction
from nailgun.utils.restrictions import RestrictionMixin
from nailgun.utils.restrictions import VmwareAttributesRestriction


class TestRestriction(base.BaseUnitTest):

    def setUp(self):
        super(TestRestriction, self).setUp()
        test_data = """
            attributes_1:
              group:
                test_attribute_1:
                  name: test_attribute_1
                  value: true
                  restrictions:
                    - condition: 'settings:group.test_attribute_2.value ==
                        true'
                      message: 'Only one of attributes 1 and 2 allowed'
                    - condition: 'settings:group.test_attribute_3.value ==
                        "spam"'
                      message: 'Only one of attributes 1 and 3 allowed'
                test_attribute_2:
                  name: test_attribute_2
                  value: true
                test_attribute_3:
                  name: test_attribute_3
                  value: spam
                  restrictions:
                    - condition: 'settings:group.test_attribute_3.value ==
                        settings:group.test_attribute_4.value'
                      message: 'Only one of attributes 3 and 4 allowed'
                      action: enable
                test_attribute_4:
                  name: test_attribute_4
                  value: spam
        """
        self.data = yaml.load(test_data)

    def tearDown(self):
        super(TestRestriction, self).tearDown()

    def test_check_restrictions(self):
        attributes = self.data.get('attributes_1')

        for gkey, gvalue in six.iteritems(attributes):
            for key, value in six.iteritems(gvalue):
                result = RestrictionMixin.check_restrictions(
                    models={'settings': attributes},
                    restrictions=value.get('restrictions', []))
                # check when couple restrictions true for some item
                if key == 'test_attribute_1':
                    self.assertTrue(result.get('result'))
                    self.assertEqual(
                        result.get('message'),
                        'Only one of attributes 1 and 2 allowed. ' +
                        'Only one of attributes 1 and 3 allowed')
                # check when different values uses in restriction
                if key == 'test_attribute_3':
                    self.assertTrue(result.get('result'))
                    self.assertEqual(
                        result.get('message'),
                        'Only one of attributes 3 and 4 allowed')

    def test_expand_restriction_format(self):
        string_restriction = 'settings.some_attribute.value != true'
        dict_restriction_long_format = {
            'condition': 'settings.some_attribute.value != true',
            'message': 'Another attribute required'
        }
        dict_restriction_short_format = {
            'settings.some_attribute.value != true':
            'Another attribute required'
        }
        result = {
            'action': 'disable',
            'condition': 'settings.some_attribute.value != true',
        }
        invalid_format = ['some_condition']

        # check string format
        self.assertDictEqual(
            RestrictionMixin._expand_restriction(
                string_restriction), result)
        result['message'] = 'Another attribute required'
        # check long format
        self.assertDictEqual(
            RestrictionMixin._expand_restriction(
                dict_restriction_long_format), result)
        # check short format
        self.assertDictEqual(
            RestrictionMixin._expand_restriction(
                dict_restriction_short_format), result)
        # check invalid format
        self.assertRaises(
            errors.InvalidData,
            RestrictionMixin._expand_restriction,
            invalid_format)


class TestAttributesObject(base.BaseTestCase):

    def setUp(self):
        super(TestAttributesObject, self).setUp()
        self.cluster = self.env.create(
            cluster_kwargs={
                'api': False
            }
        )
        attributes_metadata = """
            editable:
                access:
                  user:
                    value: ""
                    type: "text"
                    regex:
                      source: '\S'
                      error: "Invalid username"
                  email:
                    value: "admin@localhost"
                    type: "text"
                    regex:
                      source: '\S'
                      error: "Invalid email"
                  tenant:
                    value: ""
                    type: "text"
                    regex:
                      source: '\S'
                      error: "Invalid tenant name"
                  password:
                    value: "secret"
                    type: "password"
                    regex:
                      source: '\S'
                      error: "Empty password"
        """
        self.attributes_data = yaml.load(attributes_metadata)

    def test_check_with_invalid_values(self):
        objects.Cluster.update_attributes(
            self.cluster, self.attributes_data)
        attributes = objects.Cluster.get_attributes(self.cluster)
        models = {
            'settings': attributes.editable,
            'default': attributes.editable,
        }

        errs = AttributesRestriction.check_data(
            models, attributes.editable)
        self.assertItemsEqual(
            errs, ['Invalid username', 'Invalid tenant name'])

    def test_check_with_valid_values(self):
        access = self.attributes_data['editable']['access']
        access['user']['value'] = 'admin'
        access['tenant']['value'] = 'test'

        objects.Cluster.update_attributes(
            self.cluster, self.attributes_data)
        attributes = objects.Cluster.get_attributes(self.cluster)
        models = {
            'settings': attributes.editable,
            'default': attributes.editable,
        }

        errs = AttributesRestriction.check_data(
            models, attributes.editable)
        self.assertListEqual(errs, [])


class TestVmwareAttributesObject(base.BaseTestCase):

    def setUp(self):
        super(TestVmwareAttributesObject, self).setUp()
        self.cluster = self.env.create(
            cluster_kwargs={
                'api': False
            }
        )
        self.vm_data = self.env.read_fixtures(['vmware_attributes'])[0]

    def test_check_data_with_empty_values_without_restrictions(self):
        attributes = objects.Cluster.get_attributes(self.cluster).editable
        attributes['common']['use_vcenter']['value'] = True
        attributes['storage']['images_vcenter']['value'] = True
        vmware_attributes = self.vm_data.copy()
        empty_values = {
            "availability_zones": [
                {
                    "az_name": "",
                    "vcenter_host": "",
                    "vcenter_username": "",
                    "vcenter_password": "",
                    "nova_computes": [
                        {
                            "vsphere_cluster": "",
                            "service_name": "",
                            "datastore_regex": ""
                        }
                    ],
                    "cinder": {
                        "enable": True
                    }
                }
            ],
            "network": {
                "esxi_vlan_interface": ""
            },
            "glance": {
                "vcenter_host": "",
                "vcenter_username": "",
                "vcenter_password": "",
                "datacenter": "",
                "datastore": ""
            }
        }
        # Update value with empty value
        vmware_attributes['editable']['value'] = empty_values
        models = {
            'settings': attributes,
            'default': vmware_attributes['editable'],
            'cluster': self.cluster,
            'version': settings.VERSION,
            'networking_parameters': self.cluster.network_config
        }

        errs = VmwareAttributesRestriction.check_data(
            models=models,
            metadata=vmware_attributes['editable']['metadata'],
            data=vmware_attributes['editable']['value'])
        self.assertItemsEqual(
            errs,
            ['Empty cluster', 'Empty host', 'Empty username',
             'Empty password', 'Empty datacenter', 'Empty datastore'])

    def test_check_data_with_invalid_values_without_restrictions(self):
        # Disable restrictions
        attributes = objects.Cluster.get_attributes(self.cluster).editable
        attributes['common']['use_vcenter']['value'] = True
        attributes['storage']['images_vcenter']['value'] = True
        # value data taken from fixture one cluster of
        # nova computes left empty
        vmware_attributes = self.vm_data.copy()
        models = {
            'settings': attributes,
            'default': vmware_attributes['editable'],
            'cluster': self.cluster,
            'version': settings.VERSION,
            'networking_parameters': self.cluster.network_config
        }

        errs = VmwareAttributesRestriction.check_data(
            models=models,
            metadata=vmware_attributes['editable']['metadata'],
            data=vmware_attributes['editable']['value'])
        self.assertItemsEqual(errs, ['Empty cluster'])

    def test_check_data_with_invalid_values_and_with_restrictions(self):
        attributes = objects.Cluster.get_attributes(self.cluster).editable
        # fixture have restrictions enabled for glance that's why
        # only 'Empty cluster' should returned
        vmware_attributes = self.vm_data.copy()
        models = {
            'settings': attributes,
            'default': vmware_attributes['editable'],
            'cluster': self.cluster,
            'version': settings.VERSION,
            'networking_parameters': self.cluster.network_config
        }

        errs = VmwareAttributesRestriction.check_data(
            models=models,
            metadata=vmware_attributes['editable']['metadata'],
            data=vmware_attributes['editable']['value'])
        self.assertItemsEqual(errs, ['Empty cluster'])

    def test_check_data_with_valid_values_and_with_restrictions(self):
        attributes = objects.Cluster.get_attributes(self.cluster).editable
        vmware_attributes = self.vm_data.copy()
        # Set valid data for clusters
        for i, azone in enumerate(
                vmware_attributes['editable']['value']['availability_zones']):
            for j, ncompute in enumerate(azone['nova_computes']):
                ncompute['vsphere_cluster'] = 'cluster-{0}-{1}'.format(i, j)

        models = {
            'settings': attributes,
            'default': vmware_attributes['editable'],
            'cluster': self.cluster,
            'version': settings.VERSION,
            'networking_parameters': self.cluster.network_config
        }

        errs = VmwareAttributesRestriction.check_data(
            models=models,
            metadata=vmware_attributes['editable']['metadata'],
            data=vmware_attributes['editable']['value'])
        self.assertItemsEqual(errs, [])

    def test_check_data_with_valid_values_and_without_restrictions(self):
        # Disable restrictions
        attributes = objects.Cluster.get_attributes(self.cluster).editable
        attributes['common']['use_vcenter']['value'] = True
        attributes['storage']['images_vcenter']['value'] = True
        vmware_attributes = self.vm_data.copy()
        # Set valid data for clusters
        for i, azone in enumerate(
                vmware_attributes['editable']['value']['availability_zones']):
            for j, ncompute in enumerate(azone['nova_computes']):
                ncompute['vsphere_cluster'] = 'cluster-{0}-{1}'.format(i, j)
        # Set valid data for glance
        glance = vmware_attributes['editable']['value']['glance']
        glance['datacenter'] = 'test_datacenter'
        glance['datastore'] = 'test_datastore'
        models = {
            'settings': attributes,
            'default': vmware_attributes['editable'],
            'cluster': self.cluster,
            'version': settings.VERSION,
            'networking_parameters': self.cluster.network_config
        }

        errs = VmwareAttributesRestriction.check_data(
            models=models,
            metadata=vmware_attributes['editable']['metadata'],
            data=vmware_attributes['editable']['value'])
        self.assertItemsEqual(errs, [])
