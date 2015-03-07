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

from nailgun.db.sqlalchemy.models import Cluster
from nailgun.orchestrator.provisioning_serializers import \
    ProvisioningSerializer
from nailgun.test import base


class TestFaultTolerance(base.BaseTestCase):
    def test_generating_fault_tolerance_data(self):
        cluster = self.env.create(
            nodes_kwargs=[
                {'roles': ['controller']},
                {'roles': ['controller']},
                {'roles': ['controller', 'cinder']},
                {'roles': ['compute', 'cinder']},
                {'roles': ['compute']},
                {'roles': ['cinder']}])

        cluster_db = self.db.query(Cluster).get(cluster['id'])
        uids = [node.uid for node in cluster_db.nodes
                if 'compute' in node.roles]

        correct_res = [{'uids': uids, 'percentage': 2}]
        res = ProvisioningSerializer.fault_tolerance(cluster_db,
                                                     cluster_db.nodes)
        self.assertEqual(res, correct_res)
