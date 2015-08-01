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

from oslo_serialization import jsonutils

from nailgun.api.v1.validators.network import NetworkConfigurationValidator
from nailgun.errors import errors
from nailgun.test.base import BaseTestCase


class TestNetworkConfigurationValidator(BaseTestCase):

    def setUp(self):
        super(TestNetworkConfigurationValidator, self).setUp()

        cluster = self.env.create(
            cluster_kwargs={
                "api": False,
                "net_provider": "neutron"
            },
            nodes_kwargs=[
                {"api": False,
                 "pending_addition": True},
            ]
        )

        self.config = self.env.neutron_networks_get(cluster.id).json_body
        self.validator = NetworkConfigurationValidator

    def get_config(self):
        return jsonutils.dumps(self.config)

    def find_net_by_name(self, name):
        for net in self.config['networks']:
            if net['name'] == name:
                return net

    def assertRaisesInvalidData(self, message):
        with self.assertRaises(errors.InvalidData) as context:
            self.validator.validate_networks_update(self.get_config())
        self.assertIn(message, context.exception.message)

    def assertNotRaisesInvalidData(self):
        self.assertNotRaises(
            errors.InvalidData,
            self.validator.validate_networks_update,
            self.get_config())

    def test_validate_networks_is_array(self):
        self.config['networks'] = "networks"
        self.assertRaisesInvalidData(
            "'networks' is expected to be an array")

    def test_validate_network_id(self):
        mgmt = self.find_net_by_name('management')
        mgmt.pop('id')
        self.assertRaisesInvalidData(
            "No 'id' param is present for ")

    def test_validate_network_notation(self):
        mgmt = self.find_net_by_name('management')
        mgmt['meta']['notation'] = 'notation'
        self.assertRaisesInvalidData(
            "Invalid notation 'notation' was specified for network")

    def test_validate_network_cidr(self):
        mgmt = self.find_net_by_name('management')
        mgmt['cidr'] = 'a.b.c.d'
        mgmt['meta']['notation'] = 'cidr'
        self.assertRaisesInvalidData(
            "Invalid CIDR 'a.b.c.d' was specified for network "
            "{0}".format(mgmt['id']))

        mgmt['meta']['notation'] = 'ip_ranges'
        self.assertRaisesInvalidData(
            "Invalid CIDR 'a.b.c.d' was specified for network "
            "{0}".format(mgmt['id']))

    def test_validate_network_no_cidr(self):
        mgmt = self.find_net_by_name('management')
        mgmt['cidr'] = None
        mgmt['meta']['notation'] = 'cidr'
        self.assertRaisesInvalidData(
            "Invalid CIDR 'None' was specified for network "
            "{0}".format(mgmt['id']))

        mgmt['meta']['notation'] = None
        self.assertRaisesInvalidData(
            "Invalid CIDR 'None' was specified for network "
            "{0}".format(mgmt['id']))

    def test_validate_network_no_cidr_no_notation(self):
        mgmt = self.find_net_by_name('management')
        mgmt['meta'].pop('notation')
        mgmt['meta'].pop('cidr')
        self.assertNotRaisesInvalidData()

    def test_validate_network_ip_ranges(self):
        mgmt = self.find_net_by_name('management')
        mgmt['meta']['notation'] = 'ip_ranges'
        mgmt['ip_ranges'] = None
        self.assertRaisesInvalidData(
            "Invalid IP ranges 'None' were specified for network "
            "{0}".format(mgmt['id']))

        mgmt['ip_ranges'] = ['1.1.1.11']
        self.assertRaisesInvalidData(
            "Invalid IP ranges '[u'1.1.1.11']' were specified for network "
            "{0}".format(mgmt['id']))

        mgmt['ip_ranges'] = ['1.1.1.11', '1.1.1.22']
        self.assertRaisesInvalidData(
            "Invalid IP ranges '[u'1.1.1.11', u'1.1.1.22']' were specified "
            "for network {0}".format(mgmt['id']))

        mgmt['ip_ranges'] = [['1.1.1.11', '1.1.1.']]
        self.assertRaisesInvalidData(
            "Invalid IP ranges '[[u'1.1.1.11', u'1.1.1.']]' were specified "
            "for network {0}".format(mgmt['id']))
