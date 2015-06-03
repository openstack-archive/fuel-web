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
import yaml

from oslo.serialization import jsonutils

from nailgun import consts
from nailgun import objects
from nailgun.db.sqlalchemy import models
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestVMs(BaseIntegrationTest):

    def setUp(self):
        super(TestVMs, self).setUp()
        self.cluster = self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[
                {'roles': ['compute']},
                {'roles': ['compute']},
                {'roles': ['compute']}])

    def test_create_vms(self):
        self.app.post(reverse(
            'VirtualMachinesRequestHandler',
            kwargs={'obj_id': self.cluster.nodes[0].id}),
            jsonutils.dumps({'vms_number': 2}))
        resp = self.app.get(reverse(
            'VirtualMachinesRequestHandler',
            kwargs={'obj_id': self.cluster.nodes[0].id}))
        self.assertEqual(len(resp.json), 2)


class TestPredeploymentVMs(BaseIntegrationTest):
    TASKS = """
    - id: some_task
      type: puppet
      groups: [primary-controller, controller, cinder, mongo]
      required_for: [deploy_end]
      requires: [netconfig]
      parameters:
        puppet_manifest: /etc/puppet/modules/osnailyfag/netconfig.pp

    - id: netconfig
      type: puppet
      groups: [primary-controller, controller, cinder, mongo]
      required_for: [deploy_end]
      requires: [tools]
      parameters:
        puppet_manifest: /etc/puppet/modules/osnailyfag/netconfig.pp
        puppet_modules: /etc/puppet/modules
        timeout: 3600
      test_pre:
        cmd: ruby /etc/puppet/modules/o/netconfig_pre.rb
      test_post:
        cmd: ruby /etc/puppet/modules/osnailyfactenetconfig_post.rb

    - id: upload_vms_info
      type: upload_files
      role: [compute]
      required_for: [create_vms]
      requires: [netconfig]
      parameters:
        template_path: /etc/puppet/modules/cluster/template.xml
        dst: /var/lib/vms/

    - id: create_vms
      type: shell
      groups: [compute]
      requires: [upload_vms_info]
      parameters:
       cmd: sh /etc/puppet/modules/cluster/generate_vms.sh
       timeout: 180


    """

    def setUp(self):
        super(TestPredeploymentVMs, self).setUp()
        self.cluster = self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[
                {'roles': ['compute']},
                {'roles': ['compute']},
                {'roles': ['compute']}])
        objects.VirtualMachinesRequestsCollection.create(
            {'node_id': self.cluster.nodes[0].id,
             'cluster_id': self.cluster.id})
        objects.VirtualMachinesRequestsCollection.create(
            {'node_id': self.cluster.nodes[1].id,
             'cluster_id': self.cluster.id})
        self.cluster.deployment_tasks = yaml.load(self.TASKS)

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_prepare_deploy(self, mcast):
        for node in self.cluster.nodes:
            node.status = consts.NODE_STATUSES.provisioned
            node.pending_addition = False

        self.db.add_all(self.cluster.nodes)
        self.db.flush()
        out = self.app.put(reverse(
            "PrepareDeployHandler", kwargs={'cluster_id': self.cluster.id}))
        self.assertEqual(out.status_code, 200)

        args, kwargs = mcast.call_args
        import pytest; pytest.set_trace()
        deployed_uids = [n['uid'] for n in args[1]['args']['deployment_info']]
        deployment_data = args[1]['args']['deployment_info'][0]
        self.assertEqual(deployed_uids, self.node_uids)
        self.assertEqual(len(deployment_data['tasks']), 1)
