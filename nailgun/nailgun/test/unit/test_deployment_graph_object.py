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
import mock

from nailgun.db.sqlalchemy import models
from nailgun import objects
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


THREE_TASKS = [
    {
        'id': 'first',
        'type': 'puppet'
    },
    {
        'id': 'second',
        'type': 'puppet'
    },
    {
        'id': 'third',
        'type': 'puppet'
    }
]

ONE_TASK = [
    {
        'id': 'only',
        'type': 'puppet'
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

        deployment_graph = DeploymentGraph.create(
            JSON_TASKS, name='test_graph')
        serialized = DeploymentGraph.to_dict(deployment_graph)
        self.assertEqual(serialized['name'], 'test_graph')
        self.assertItemsEqual(serialized['deployment_tasks'], expected_tasks)

    @mock.patch('nailgun.logger.logger.debug')
    def test_deletion_with_single_relation(self, m_debug):
        self.env.create()

        # this asserts just showing vanilla environment state
        self.assertModelCount(models.DeploymentGraph, 1)
        self.assertModelCount(models.DeploymentGraphTask, 25)
        self.assertModelCount(models.Cluster, 1)
        self.assertModelCount(models.Release, 1)
        self.assertModelCount(models.ClusterDeploymentGraph, 0)
        self.assertModelCount(models.PluginDeploymentGraph, 0)
        self.assertModelCount(models.ReleaseDeploymentGraph, 1)

        cluster = self.env.clusters[0]

        one_task_deployment_graph = DeploymentGraph.create(
            ONE_TASK, name='test_graph')
        one_task_deployment_graph_id = one_task_deployment_graph.id
        DeploymentGraph.attach_to_model(
            one_task_deployment_graph, cluster, graph_type='test_type1')

        two_tasks_deployment_graph = DeploymentGraph.create(
            THREE_TASKS, name='test_graph')
        two_tasks_deployment_graph_id = two_tasks_deployment_graph.id
        DeploymentGraph.attach_to_model(
            two_tasks_deployment_graph, cluster, graph_type='test_type2')

        self.assertModelCount(models.DeploymentGraph, 3)
        self.assertModelCount(
            models.DeploymentGraphTask,
            25 + len(THREE_TASKS) + len(ONE_TASK))
        # need to be sure that no clusters or releases was deleted
        self.assertModelCount(models.Cluster, 1)
        self.assertModelCount(models.Release, 1)
        self.assertModelCount(models.ClusterDeploymentGraph, 2)
        self.assertModelCount(models.ReleaseDeploymentGraph, 1)

        # test that only one graph and relation is deleted
        DeploymentGraph.delete_from_model(cluster, graph_type='test_type2')

        self.assertModelCount(models.DeploymentGraph, 2)
        self.assertModelCount(
            models.DeploymentGraphTask, 25 + len(ONE_TASK))
        self.assertModelCount(models.Cluster, 1)
        self.assertModelCount(models.Release, 1)
        self.assertModelCount(models.ClusterDeploymentGraph, 1)
        self.assertModelCount(models.ReleaseDeploymentGraph, 1)

        m_debug.assert_called_with('Graph with ID={0} related to model '
                                   'Cluster with ID={1} was deleted'
                                   .format(two_tasks_deployment_graph_id,
                                           cluster.id))

        # test that graph and relations deletion cascades from cluster
        objects.Cluster.delete(cluster)

        self.assertModelCount(models.DeploymentGraph, 1)
        self.assertModelCount(models.DeploymentGraphTask, 25)
        self.assertModelCount(models.Cluster, 0)
        self.assertModelCount(models.Release, 1)
        self.assertModelCount(models.ClusterDeploymentGraph, 0)
        self.assertModelCount(models.ReleaseDeploymentGraph, 1)
        m_debug.assert_called_with(
            "Orphan graphs with ID={0} have been removed"
            .format([one_task_deployment_graph_id]))

    @mock.patch('nailgun.logger.logger.debug')
    def test_replacement(self, m_debug):
        self.env.create()
        cluster = self.env.clusters[0]

        one_task_deployment_graph = DeploymentGraph.create(
            ONE_TASK, name='test_graph')
        one_task_deployment_graph_id = one_task_deployment_graph.id
        DeploymentGraph.attach_to_model(
            one_task_deployment_graph, cluster, graph_type='test_type1')

        self.assertModelCount(models.DeploymentGraph, 2)
        self.assertModelCount(models.DeploymentGraphTask, 25 + len(ONE_TASK))
        self.assertModelCount(models.Cluster, 1)
        self.assertModelCount(models.ClusterDeploymentGraph, 1)

        two_tasks_deployment_graph = DeploymentGraph.create(
            THREE_TASKS, name='test_graph')
        DeploymentGraph.attach_to_model(
            two_tasks_deployment_graph, cluster, graph_type='test_type1')

        m_debug.assert_called_with(
            'Graph with ID={0} related to model '
            'Cluster with ID={1} was deleted'
            .format(one_task_deployment_graph_id, cluster.id))

        self.assertModelCount(models.DeploymentGraph, 2)
        self.assertModelCount(
            models.DeploymentGraphTask, 25 + len(THREE_TASKS))
        self.assertModelCount(models.Cluster, 1)
        self.assertModelCount(models.ClusterDeploymentGraph, 1)

    @mock.patch('nailgun.logger.logger.warning')
    @mock.patch('nailgun.logger.logger.debug')
    def test_non_deletion_when_many_relations(self, m_debug, m_warn):
        self.env.create()
        self.assertModelCount(models.DeploymentGraph, 1)
        cluster = self.env.clusters[0]
        deployment_graph = DeploymentGraph.create(
            JSON_TASKS, name='test_graph')
        DeploymentGraph.attach_to_model(
            deployment_graph, cluster, graph_type='test_graph')
        DeploymentGraph.attach_to_model(
            deployment_graph, cluster.release, graph_type='test_graph')
        self.assertModelCount(models.DeploymentGraph, 2)
        self.assertModelCount(models.ClusterDeploymentGraph, 1)
        self.assertModelCount(models.ReleaseDeploymentGraph, 2)
        DeploymentGraph.delete_from_model(cluster, graph_type='test_graph')
        m_warn.assert_called_with('Graph with ID={0} have many relations, so '
                                  'it will be detached but not deleted to '
                                  'save other relations'
                                  .format(deployment_graph.id))

        m_debug.assert_called_with('Graph with ID={0} was detached from model '
                                   'Cluster with ID={1}'
                                   .format(deployment_graph.id, cluster.id))
        self.assertModelCount(models.DeploymentGraph, 2)
        self.assertModelCount(models.ClusterDeploymentGraph, 0)
        self.assertModelCount(models.ReleaseDeploymentGraph, 2)
