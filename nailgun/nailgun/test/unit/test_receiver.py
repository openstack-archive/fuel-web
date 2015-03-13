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

from nailgun.rpc.receiver import NailgunReceiver
from nailgun.objects import Plugin
from nailgun.test import base


class TestNailgunReceiver(base.BaseTestCase):

    def setUp(self):
        super(TestNailgunReceiver, self).setUp()

        self.env.create(
            status='operational',
            nodes_kwargs=[
                {'roles': 'controller', 'status': 'ready'}])
        self.cluster = self.env.clusters[0]

        for i in range(2):
            meta = self.env.get_default_plugin_metadata(
                name='name{0}'.format(i),
                title='title{0}'.format(i),
                description='description{0}'.format(i))

            self.plugin = Plugin.create(meta)
            self.cluster.plugins.append(self.plugin)

        self.task = self.env.create_task(
            name='deployment',
            status='ready',
            cluster_id=self.cluster.id)

    def test_success_action_with_plugins(self):
        NailgunReceiver._success_action(self.task, 'ready', 100)
        self.assertRegexpMatches(
            self.task.message,
            "Deployment of environment '[^\s]+' is done. Access the OpenStack "
            "dashboard \(Horizon\) at [^\s]+\n"
            "\n"
            "Plugin name\d is deployed. description\d\n"
            "Plugin name\d is deployed. description\d")
