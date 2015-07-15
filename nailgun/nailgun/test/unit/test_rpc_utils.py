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

import mock

from nailgun import consts
from nailgun.rpc import utils
from nailgun.test import base


class TestRpcUtils(base.BaseTestCase):

    def test_get_protocol_for_horizon(self):
        self.env.create()
        cluster = self.env.clusters[0]

        self.assertIn(
            cluster.attributes.editable['public_ssl']['horizon']['value'],
            (True, True)
        )

        with mock.patch.dict(cluster.attributes.editable, {}):
            self.assertEqual(consts.PROTOCOL.https,
                             utils.get_protocol_for_horizon(cluster))

        with mock.patch.dict(cluster.attributes.editable, {'public_ssl': {}}):
            self.assertEqual(consts.PROTOCOL.http,
                             utils.get_protocol_for_horizon(cluster))

        with mock.patch.dict(cluster.attributes.editable,
                             {'public_ssl': {'horizon': {}}}):
            self.assertEqual(consts.PROTOCOL.http,
                             utils.get_protocol_for_horizon(cluster))

        with mock.patch.dict(cluster.attributes.editable,
                             {'public_ssl': {'horizon': {'value': False}}}):
            self.assertEqual(consts.PROTOCOL.http,
                             utils.get_protocol_for_horizon(cluster))

        with mock.patch.dict(cluster.attributes.editable,
                             {'public_ssl': {'horizon': {'value': None}}}):
            self.assertEqual(consts.PROTOCOL.http,
                             utils.get_protocol_for_horizon(cluster))

        with mock.patch.dict(cluster.attributes.editable,
                             {'public_ssl': {'horizon': {'value': True}}}):
            self.assertEqual(consts.PROTOCOL.http,
                             utils.get_protocol_for_horizon(cluster))
