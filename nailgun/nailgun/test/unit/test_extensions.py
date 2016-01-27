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

from nailgun.errors import errors
from nailgun.extensions import BaseExtension
from nailgun.extensions import BaseExtensionPipeline
from nailgun.extensions import fire_callback_on_cluster_delete
from nailgun.extensions import fire_callback_on_node_collection_delete
from nailgun.extensions import fire_callback_on_node_create
from nailgun.extensions import fire_callback_on_node_delete
from nailgun.extensions import fire_callback_on_node_reset
from nailgun.extensions import fire_callback_on_node_update
from nailgun.extensions import get_extension
from nailgun.extensions import node_extension_call
from nailgun.orchestrator import deployment_graph
from nailgun.orchestrator import deployment_serializers
from nailgun.orchestrator import provisioning_serializers
from nailgun.test.base import BaseTestCase


class TestBaseExtension(BaseTestCase):

    def setUp(self):
        super(TestBaseExtension, self).setUp()

        class Extension(BaseExtension):
            name = 'ext_name'
            version = '1.0.0'
            description = 'ext description'

        self.extension = Extension()

    def test_alembic_table_version(self):
        self.assertEqual(
            self.extension.alembic_table_version(),
            'ext_name_alembic_version')

    def test_table_prefix(self):
        self.assertEqual(
            self.extension.table_prefix(),
            'ext_name_')

    def test_alembic_migrations_path_none_by_default(self):
        self.assertIsNone(self.extension.alembic_migrations_path())

    def test_full_name(self):
        self.assertEqual(
            self.extension.full_name(),
            'ext_name-1.0.0')


def make_mock_extensions(names=('ex1', 'ex2')):
    mocks = []
    for name in names:
        # NOTE(eli): since 'name' is reserved world
        # for mock constructor, we should assign
        # name explicitly
        ex_m = mock.MagicMock()
        ex_m.name = name
        ex_m.provides = ['method_call']
        mocks.append(ex_m)

    return mocks


class TestExtensionUtils(BaseTestCase):

    def make_node(self, node_extensions=[], cluster_extensions=[]):
        node = mock.MagicMock()
        node.extensions = node_extensions
        node.cluster.extensions = cluster_extensions

        return node

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_get_extension(self, get_m):
        extension = get_extension('ex1')
        self.assertEqual(extension.name, 'ex1')

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_get_extension_raises_errors(self, get_m):
        self.assertRaisesRegexp(
            errors.CannotFindExtension,
            "Cannot find extension with name 'unknown_ex'",
            get_extension,
            'unknown_ex')

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_node_extension_call_raises_error(self, _):
        self.assertRaisesRegexp(
            errors.CannotFindExtension,
            "Cannot find extension which provides 'method_call' call",
            node_extension_call,
            'method_call',
            self.make_node())

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_node_extension_call_extension_from_node(self, get_m):
        node = self.make_node(
            node_extensions=['ex1'],
            cluster_extensions=['ex2'])

        node_extension_call('method_call', node)
        ex1 = get_m.return_value[0]
        self.assertEqual('ex1', ex1.name)
        ex2 = get_m.return_value[1]
        self.assertEqual('ex2', ex2.name)

        ex1.method_call.assert_called_once_with(node)
        self.assertFalse(ex2.method_call.called)

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_node_extension_call_default_extension_from_cluster(self, get_m):
        node = self.make_node(
            node_extensions=[],
            cluster_extensions=['ex2'])

        node_extension_call('method_call', node)
        ex1 = get_m.return_value[0]
        self.assertEqual('ex1', ex1.name)
        ex2 = get_m.return_value[1]
        self.assertEqual('ex2', ex2.name)

        self.assertFalse(ex1.method_call.called)
        ex2.method_call.assert_called_once_with(node)

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_fire_callback_on_node_create(self, get_m):
        node = mock.MagicMock()
        fire_callback_on_node_create(node)

        for ext in get_m.return_value:
            ext.on_node_create.assert_called_once_with(node)

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_fire_callback_on_node_update(self, get_m):
        node = mock.MagicMock()
        fire_callback_on_node_update(node)

        for ext in get_m.return_value:
            ext.on_node_update.assert_called_once_with(node)

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_fire_callback_on_node_reset(self, get_m):
        node = mock.MagicMock()
        fire_callback_on_node_reset(node)

        for ext in get_m.return_value:
            ext.on_node_reset.assert_called_once_with(node)

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_fire_callback_on_node_delete(self, get_m):
        node = mock.MagicMock()
        fire_callback_on_node_delete(node)

        for ext in get_m.return_value:
            ext.on_node_delete.assert_called_once_with(node)

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_fire_callback_on_node_collection_delete(self, get_m):
        node_ids = [1, 2, 3, 4]
        fire_callback_on_node_collection_delete(node_ids)

        for ext in get_m.return_value:
            ext.on_node_collection_delete.assert_called_once_with(node_ids)

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_fire_callback_on_cluster_deletion(self, get_m):
        cluster = mock.MagicMock()
        fire_callback_on_cluster_delete(cluster)

        for ext in get_m.return_value:
            ext.on_cluster_delete.assert_called_once_with(cluster)


class TestPipeline(TestBaseExtension):

    def _create_cluster_with_extensions(self):
        self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'roles': ['controller'], 'pending_addition': True}]
        )
        cluster = self.env.clusters[0]
        cluster.extensions = [self.extension.name, 'volume_manager']
        self.db.flush()

        return cluster

    @mock.patch('nailgun.orchestrator.deployment_serializers.'
                'fire_callback_on_deployment_data_serialization')
    def test_deployment_serialization(self, mfire_callback):
        cluster = self._create_cluster_with_extensions()
        graph = deployment_graph.AstuteGraph(cluster)
        deployment_serializers.serialize(graph, cluster, cluster.nodes)

        self.assertTrue(mfire_callback.called)
        self.assertEqual(mfire_callback.call_args[1], {
            'cluster': cluster,
            'nodes': cluster.nodes,
        })

    @mock.patch.object(deployment_graph.AstuteGraph, 'deploy_task_serialize')
    def test_deployment_serialization_ignore_customized(self, _):
        cluster = self._create_cluster_with_extensions()
        graph = deployment_graph.AstuteGraph(cluster)

        # There are some changes in deployment data, and we don't ignore them
        # so pipelines should not be called. Happens when user has done some
        # changes to the data and run deployment.
        data = [{"role": "ole"}]

        with mock.patch('nailgun.orchestrator.deployment_serializers.'
                        'fire_callback_on_deployment_data_serialization'
                        ) as mfire_callback:
            with mock.patch.object(
                    cluster.nodes[0], 'replaced_deployment_info',
                    new_callable=mock.Mock(return_value=data)):

                deployment_serializers.serialize(graph, cluster, cluster.nodes)

        self.assertFalse(mfire_callback.called)

        # There are no changes in deployment data so pipelines can be called.
        # We implicitly ignore any changes, but it doesn't matter here.
        # Happens when user hasn't done any changes, and just run deploy.
        with mock.patch('nailgun.orchestrator.deployment_serializers.'
                        'fire_callback_on_deployment_data_serialization'
                        ) as mfire_callback:
            with mock.patch.object(
                    cluster.nodes[0], 'replaced_deployment_info',
                    new_callable=mock.Mock(return_value=[])):

                deployment_serializers.serialize(graph, cluster, cluster.nodes)

        self.assertTrue(mfire_callback.called)

        # There are some changes in deployment data, but we ignore them,
        # so pipelines can be called. Happens when user wants to download
        # default deployment data after making some changes already.
        with mock.patch('nailgun.orchestrator.deployment_serializers.'
                        'fire_callback_on_deployment_data_serialization'
                        ) as mfire_callback:
            with mock.patch.object(
                    cluster.nodes[0], 'replaced_deployment_info',
                    new_callable=mock.Mock(return_value=data)):

                deployment_serializers.serialize(
                    graph, cluster, cluster.nodes, ignore_customized=True)

        self.assertTrue(mfire_callback.called)

        # There are no changes in deployment data. We implicitly don't ignore
        # any changes, but because there is no changes pipelines can be called.
        with mock.patch('nailgun.orchestrator.deployment_serializers.'
                        'fire_callback_on_deployment_data_serialization'
                        ) as mfire_callback:
            with mock.patch.object(
                    cluster.nodes[0], 'replaced_deployment_info',
                    new_callable=mock.Mock(return_value=[])):

                deployment_serializers.serialize(
                    graph, cluster, cluster.nodes, ignore_customized=True)

        self.assertTrue(mfire_callback.called)

    def test_provisioning_serialization_ignore_customized(self):
        cluster = self._create_cluster_with_extensions()

        # There are some changes in provisioning data, and we don't ignore them
        # so pipelines should not be called. Happens when user has done some
        # changes to the data and run provisioning.
        data = {"role": "ole"}

        with mock.patch('nailgun.orchestrator.provisioning_serializers.'
                        'fire_callback_on_provisioning_data_serialization'
                        ) as mfire_callback:
            with mock.patch.object(
                    cluster.nodes[0], 'replaced_provisioning_info',
                    new_callable=mock.Mock(return_value=data)):

                provisioning_serializers.serialize(cluster, cluster.nodes)

        self.assertFalse(mfire_callback.called)

        # There are no changes in provisioning data so pipelines can be called.
        # We implicitly ignore any changes, but it doesn't matter here.
        # Happens when user hasn't done any changes, and just run deploy.
        with mock.patch('nailgun.orchestrator.provisioning_serializers.'
                        'fire_callback_on_provisioning_data_serialization'
                        ) as mfire_callback:
            with mock.patch.object(
                    cluster.nodes[0], 'replaced_provisioning_info',
                    new_callable=mock.Mock(return_value={})):

                provisioning_serializers.serialize(cluster, cluster.nodes)

        self.assertTrue(mfire_callback.called)

        # There are some changes in provisioning data, but we ignore them,
        # so pipelines can be called. Happens when user wants to download
        # default provisioning data after making some changes already.
        with mock.patch('nailgun.orchestrator.provisioning_serializers.'
                        'fire_callback_on_provisioning_data_serialization'
                        ) as mfire_callback:
            with mock.patch.object(
                    cluster.nodes[0], 'replaced_provisioning_info',
                    new_callable=mock.Mock(return_value=data)):

                provisioning_serializers.serialize(
                    cluster, cluster.nodes, ignore_customized=True)

        self.assertTrue(mfire_callback.called)

        # There are no changes in provisioning data. We implicitly don't ignore
        # any changes, but because there is no changes pipelines can be called.
        with mock.patch('nailgun.orchestrator.provisioning_serializers.'
                        'fire_callback_on_provisioning_data_serialization'
                        ) as mfire_callback:
            with mock.patch.object(
                    cluster.nodes[0], 'replaced_provisioning_info',
                    new_callable=mock.Mock(return_value={})):

                provisioning_serializers.serialize(
                    cluster, cluster.nodes, ignore_customized=True)

        self.assertTrue(mfire_callback.called)

    @mock.patch('nailgun.orchestrator.provisioning_serializers.'
                'fire_callback_on_provisioning_data_serialization')
    def test_provisioning_serialization(self, mfire_callback):
        cluster = self._create_cluster_with_extensions()
        provisioning_serializers.serialize(cluster, cluster.nodes)

        self.assertTrue(mfire_callback.called)
        self.assertEqual(mfire_callback.call_args[1], {
            'cluster': cluster,
            'nodes': cluster.nodes,
        })

    @mock.patch('nailgun.extensions.base.BaseExtensionPipeline.'
                'process_provisioning')
    def test_process_provisioning(self, mprocess):
        cluster = self._create_cluster_with_extensions()
        provisioning_serializers.serialize(cluster, cluster.nodes)
        self.assertTrue(mprocess.called)

    @mock.patch('nailgun.extensions.base.BaseExtensionPipeline.'
                'process_deployment')
    def test_process_deployment(self, mprocess):
        cluster = self._create_cluster_with_extensions()
        graph = deployment_graph.AstuteGraph(cluster)
        deployment_serializers.serialize(graph, cluster, cluster.nodes)
        self.assertTrue(mprocess.called)

    def test_pipeline_change_data(self):
        self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'roles': ['controller'], 'pending_addition': True}]
        )
        cluster = self.env.clusters[0]
        cluster.extensions = [self.extension.name]
        self.db.flush()

        class PipelinePlus1(BaseExtensionPipeline):

            @classmethod
            def process_provisioning(cls, data, **kwargs):
                data['key'] += 1

        class PipelinePlus2(BaseExtensionPipeline):

            @classmethod
            def process_provisioning(cls, data, **kwargs):
                data['key'] += 2

        class PipelinePlus3(BaseExtensionPipeline):

            @classmethod
            def process_deployment(cls, data, **kwargs):
                data['key'] += 3

        class Extension(BaseExtension):
            name = 'ext_name'
            version = '1.0.0'
            description = 'ext description'
            data_pipelines = (PipelinePlus1, PipelinePlus2, PipelinePlus3)

        extension = Extension()

        data = {'key': 0}

        mserializer = mock.MagicMock()
        mserializer.serialize.return_value = data

        with mock.patch('nailgun.extensions.manager.get_all_extensions',
                        return_value=[extension]):
            with mock.patch('nailgun.orchestrator.provisioning_serializers.'
                            'get_serializer_for_cluster',
                            return_value=mserializer):
                provisioning_serializers.serialize(cluster, cluster.nodes)

        self.assertEqual(data['key'], 3)

        temp_ser = mock.MagicMock()
        temp_ser.serialize.return_value = data
        mserializer.return_value = temp_ser
        with mock.patch('nailgun.extensions.manager.get_all_extensions',
                        return_value=[extension]):
            with mock.patch('nailgun.orchestrator.deployment_serializers.'
                            'get_serializer_for_cluster',
                            return_value=mserializer):
                graph = deployment_graph.AstuteGraph(cluster)
                deployment_serializers.serialize(graph, cluster, cluster.nodes)

        self.assertEqual(data['key'], 6)
