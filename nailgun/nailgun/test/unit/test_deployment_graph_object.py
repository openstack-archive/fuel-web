# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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

from nailgun.objects.deployment_graph import DeploymentGraph
from nailgun.test import base

JSON_TASKS = [
    {
        'id': 'post_deployment_end',
        'type': 'stage',
        'requires': ['post_deployment_start']
    },
    {
        'id': 'primary-controller',
        'parameters': {'strategy': {'type': 'one_by_one'}},
        'required_for': ['deploy_end'],
        'requires': ['deploy_start'],
        'role': ['primary-controller'],
        'type': 'group'
    },
    {
        'id': 'cross-dep-test',
        'type': 'puppet',
        'cross-depended-by': ['a', 'b'],
        'cross-depends': ['c', 'd'],
    },
    {
        'id': 'custom-fields-test',
        'type': 'puppet',
        'CUSTOM_FIELD1': 'custom',
        'CUSTOM_FIELD2': ['custom'],
        'CUSTOM_FIELD3': {'custom': 'custom'},
    },
    {
        'id': 'ssl-keys-saving',
        'type': 'puppet',
        'version': '2.0.0',
        'groups': ['primary-controller', 'controller', 'compute',
                   'compute-vmware', 'cinder', 'cinder-vmware',
                   'primary-mongo', 'mongo', 'ceph-osd', 'virt'],
        'requires': ['firewall'],
        'condition': "(settings:public_ssl.horizon.value == true or settings:"
                     "public_ssl.services.value == true) and settings:"
                     "public_ssl.cert_source.value == 'user_uploaded'",
        'required_for': ['deploy_end'],
        'parameters': {
            'puppet_manifest': '/etc/puppet/modules/osnailyfacter/'
                               'modular/ssl/ssl_keys_saving.pp',
            'puppet_modules': '/etc/puppet/modules',
            'timeout': 3600
        },
        'test_pre': {
            'cmd': 'ruby /etc/puppet/modules/osnailyfacter/'
                   'modular/ssl/ssl_keys_saving_pre.rb'
        }
    }
]


class TestDeploymentGraphModel(base.BaseTestCase):
    def test_deployment_graph_creation(self):
        self.maxDiff = None
        expected_tasks = [
            {
                'task_name': 'cross-dep-test',
                'id': 'cross-dep-test',  # legacy
                'type': 'puppet',
                'version': '1.0.0',
                'cross_depended_by': ['a', 'b'],
                'cross_depends': ['c', 'd'],
                'cross-depended-by': ['a', 'b'],  # legacy
                'cross-depends': ['c', 'd'],      # legacy
            }, {
                'task_name': 'post_deployment_end',
                'id': 'post_deployment_end',  # legacy
                'type': 'stage',
                'version': '1.0.0',
                'requires': ['post_deployment_start'],
            }, {
                'task_name': 'primary-controller',
                'id': 'primary-controller',    # legacy
                'type': 'group',
                'version': '1.0.0',
                'required_for': ['deploy_end'],
                'requires': ['deploy_start'],
                'roles': ['primary-controller'],
                'role': ['primary-controller'],    # legacy
                'parameters': {'strategy': {'type': 'one_by_one'}},
            },
            {
                'id': 'custom-fields-test',
                'task_name': 'custom-fields-test',
                'type': 'puppet',
                'version': '1.0.0',
                'CUSTOM_FIELD1': 'custom',
                'CUSTOM_FIELD2': ['custom'],
                'CUSTOM_FIELD3': {'custom': 'custom'},
            },
            {
                'id': 'ssl-keys-saving',
                'task_name': 'ssl-keys-saving',
                'type': 'puppet',
                'version': '2.0.0',
                'groups': ['primary-controller', 'controller', 'compute',
                           'compute-vmware', 'cinder', 'cinder-vmware',
                           'primary-mongo', 'mongo', 'ceph-osd', 'virt'],
                'requires': ['firewall'],
                'condition': "(settings:public_ssl.horizon.value == true or "
                             "settings:public_ssl.services.value == true) "
                             "and settings:public_ssl.cert_source.value == "
                             "'user_uploaded'",
                'required_for': ['deploy_end'],
                'parameters': {
                    'puppet_manifest': '/etc/puppet/modules/osnailyfacter/'
                                       'modular/ssl/ssl_keys_saving.pp',
                    'puppet_modules': '/etc/puppet/modules',
                    'timeout': 3600
                },
                'test_pre': {
                    'cmd': 'ruby /etc/puppet/modules/osnailyfacter/'
                           'modular/ssl/ssl_keys_saving_pre.rb'
                }
            }
        ]

        dg = DeploymentGraph.create(JSON_TASKS, verbose_name='test_graph')
        serialized = DeploymentGraph.to_dict(dg)
        self.assertEqual(serialized['verbose_name'], 'test_graph')
        self.assertItemsEqual(serialized['deployment_tasks'], expected_tasks)
