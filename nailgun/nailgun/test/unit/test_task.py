# -*- coding: utf-8 -*-
#    Copyright 2013 Mirantis, Inc.
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
import six

from oslo_serialization import jsonutils
import yaml

from nailgun import consts
from nailgun.db.sqlalchemy.models import Task
from nailgun.errors import errors
from nailgun.extensions.volume_manager.manager import VolumeManager
from nailgun import objects
from nailgun.task import task
from nailgun.test import base
from nailgun.utils import reverse


class TestClusterDeletionTask(base.BaseTestCase):

    def create_cluster_and_execute_deletion_task(
            self, attributes=None, os=consts.RELEASE_OS.centos):
        self.env.create(
            cluster_kwargs={
                'editable_attributes': attributes,
            },
            release_kwargs={
                'operating_system': os,
                'version': '2025-7.0',
            },
        )
        self.fake_task = Task(name=consts.TASK_NAMES.cluster_deletion,
                              cluster=self.env.clusters[0])
        task.ClusterDeletionTask.execute(self.fake_task)

    @mock.patch('nailgun.task.task.DeletionTask', autospec=True)
    @mock.patch.object(task.DeleteIBPImagesTask, 'execute')
    def test_target_images_deletion_skipped_empty_attributes(
            self, mock_img_task, mock_del):
        self.create_cluster_and_execute_deletion_task({})
        self.assertTrue(mock_del.execute.called)
        self.assertFalse(mock_img_task.called)

    @mock.patch('nailgun.task.task.DeletionTask', autospec=True)
    @mock.patch.object(task.DeleteIBPImagesTask, 'execute')
    def test_target_images_deletion_skipped_os_centos(
            self, mock_img_task, mock_del):
        attributes = {'provision': {
            'method': consts.PROVISION_METHODS.image,
        }}
        self.create_cluster_and_execute_deletion_task(attributes)
        self.assertTrue(mock_del.execute.called)
        self.assertFalse(mock_img_task.called)

    @mock.patch('nailgun.task.task.DeletionTask', autospec=True)
    @mock.patch.object(task.DeleteIBPImagesTask, 'execute')
    def test_target_images_deletion_skipped_os_ubuntu_cobbler(
            self, mock_img_task, mock_del):
        os = consts.RELEASE_OS.ubuntu
        attributes = {'provision': {
            'method': consts.PROVISION_METHODS.cobbler,
        }}
        self.create_cluster_and_execute_deletion_task(attributes, os)
        self.assertTrue(mock_del.execute.called)
        self.assertFalse(mock_img_task.called)

    @mock.patch('nailgun.task.task.DeletionTask', autospec=True)
    @mock.patch.object(task.DeleteIBPImagesTask, 'execute')
    def test_target_images_deletion_executed(self, mock_img_task, mock_del):
        os = consts.RELEASE_OS.ubuntu
        attributes = {'provision': {
            'method': consts.PROVISION_METHODS.image,
        }}
        self.create_cluster_and_execute_deletion_task(attributes, os)
        self.assertTrue(mock_del.execute.called)
        self.assertTrue(mock_img_task.called)
        fake_attrs = objects.Attributes.merged_attrs_values(
            self.fake_task.cluster.attributes)
        mock_img_task.assert_called_once_with(
            mock.ANY, fake_attrs['provision']['image_data'])


class TestDeleteIBPImagesTask(base.BaseUnitTest):

    @mock.patch('nailgun.task.task.settings')
    @mock.patch('nailgun.task.task.make_astute_message')
    def test_message(self, mock_astute, mock_settings):
        mock_settings.PROVISIONING_IMAGES_PATH = '/fake/path'
        mock_settings.REMOVE_IMAGES_TIMEOUT = 'fake_timeout'
        task_mock = mock.Mock()
        task_mock.cluster.id = '123'
        task_mock.uuid = 'fake_uuid'
        fake_image_data = {'/': {'uri': 'http://a.b/fake.img'},
                           '/boot': {'uri': 'http://c.d/fake-boot.img'}}
        task.DeleteIBPImagesTask.message(task_mock, fake_image_data)

        rpc_message = mock_astute.call_args[0][3]
        rm_cmd = rpc_message['tasks'][0]['parameters'].pop('cmd')

        mock_astute.assert_called_once_with(
            mock.ANY, 'execute_tasks', 'remove_images_resp', mock.ANY)

        self.assertEqual(rpc_message, {
            'tasks': [{
                'id': None,
                'type': 'shell',
                'uids': [consts.MASTER_NODE_UID],
                'parameters': {
                    'retries': 3,
                    'cwd': '/',
                    'timeout': 'fake_timeout',
                    'interval': 1}}]})

        self.assertTrue(rm_cmd.startswith('rm -f'))
        self.assertIn('/fake/path/fake-boot.img', rm_cmd)
        self.assertIn('/fake/path/fake.img', rm_cmd)
        self.assertIn('/fake/path/fake.yaml', rm_cmd)


class TestHelperUpdateClusterStatus(base.BaseTestCase):

    def setUp(self):
        super(TestHelperUpdateClusterStatus, self).setUp()
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller']},
                {'roles': ['compute', 'virt']},
                {'roles': ['cinder']}])

    def node_should_be_error_with_type(self, node, error_type):
        self.assertEqual(node.status, 'error')
        self.assertEqual(node.error_type, error_type)
        self.assertEqual(node.progress, 0)

    def nodes_should_not_be_error(self, nodes):
        for node in nodes:
            self.assertEqual(node.status, 'discover')

    @property
    def cluster(self):
        return self.env.clusters[0]

    def test_update_nodes_to_error_if_deployment_task_failed(self):
        self.cluster.nodes[0].status = 'deploying'
        self.cluster.nodes[0].progress = 12
        deployment_task = Task(name='deployment', cluster=self.cluster,
                               status='error')
        self.db.add(deployment_task)
        self.db.commit()

        objects.Task._update_cluster_data(deployment_task)
        self.db.flush()

        self.assertEqual(self.cluster.status, 'error')
        self.node_should_be_error_with_type(self.cluster.nodes[0], 'deploy')
        self.nodes_should_not_be_error(self.cluster.nodes[1:])

    def test_update_cluster_to_error_if_deploy_task_failed(self):
        deploy_task = Task(name='deploy', cluster=self.cluster, status='error')
        self.db.add(deploy_task)
        self.db.commit()

        objects.Task._update_cluster_data(deploy_task)
        self.db.flush()

        self.assertEqual(self.cluster.status, 'error')

    def test_update_nodes_to_error_if_provision_task_failed(self):
        self.cluster.nodes[0].status = 'provisioning'
        self.cluster.nodes[0].progress = 12
        provision_task = Task(name='provision', cluster=self.cluster,
                              status='error')
        self.db.add(provision_task)
        self.db.commit()

        objects.Task._update_cluster_data(provision_task)
        self.db.flush()

        self.assertEqual(self.cluster.status, 'error')
        self.node_should_be_error_with_type(self.cluster.nodes[0], 'provision')
        self.nodes_should_not_be_error(self.cluster.nodes[1:])

    def test_update_cluster_to_operational(self):
        deploy_task = Task(
            name=consts.TASK_NAMES.deployment,
            cluster=self.cluster, status=consts.TASK_STATUSES.ready
        )
        for node in self.env.nodes:
            node.status = consts.NODE_STATUSES.ready
        self.db.add(deploy_task)
        self.db.commit()

        objects.Task._update_cluster_data(deploy_task)
        self.db.flush()

        self.assertEqual(
            self.cluster.status, consts.CLUSTER_STATUSES.operational)

    def test_update_if_parent_task_is_ready_all_nodes_should_be_ready(self):
        for node in self.cluster.nodes:
            node.status = consts.NODE_STATUSES.ready
            node.progress = 100

        self.cluster.nodes[0].status = consts.NODE_STATUSES.deploying
        self.cluster.nodes[0].progress = 24

        deploy_task = Task(
            name=consts.TASK_NAMES.deployment,
            cluster=self.cluster, status=consts.TASK_STATUSES.ready
        )
        self.db.add(deploy_task)
        self.db.commit()

        objects.Task._update_cluster_data(deploy_task)
        self.db.flush()

        self.assertEqual(
            self.cluster.status, consts.CLUSTER_STATUSES.operational)

        for node in self.cluster.nodes:
            self.assertEqual(node.status, consts.NODE_STATUSES.ready)
            self.assertEqual(node.progress, 100)

    def test_update_cluster_status_if_task_was_already_in_error_status(self):
        for node in self.cluster.nodes:
            node.status = 'provisioning'
            node.progress = 12

        provision_task = Task(name='provision', cluster=self.cluster,
                              status='error')
        self.db.add(provision_task)
        self.db.commit()

        data = {'status': 'error', 'progress': 100}
        objects.Task.update(provision_task, data)
        self.db.flush()

        self.assertEqual(self.cluster.status, 'error')
        self.assertEqual(provision_task.status, 'error')

        for node in self.cluster.nodes:
            self.assertEqual(node.status, 'error')
            self.assertEqual(node.progress, 0)

    def test_do_not_set_cluster_to_error_if_validation_failed(self):
        for task_name in ['check_before_deployment', 'check_networks']:
            supertask = Task(
                name='deploy',
                cluster=self.cluster,
                status='error')

            check_task = Task(
                name=task_name,
                cluster=self.cluster,
                status='error')

            supertask.subtasks.append(check_task)
            self.db.add(check_task)
            self.db.commit()

            objects.Task._update_cluster_data(supertask)
            self.db.flush()

            self.assertEqual(self.cluster.status, 'new')


class TestCheckBeforeDeploymentTask(base.BaseTestCase):

    def setUp(self):
        super(TestCheckBeforeDeploymentTask, self).setUp()
        self.env.create(
            release_kwargs={'version': '1111-8.0'},
            cluster_kwargs={
                'net_provider': 'neutron',
                'net_segment_type': 'gre'
            },
            nodes_kwargs=[{'roles': ['controller']}])

        self.env.create_node()
        self.node = self.env.nodes[0]
        self.cluster = self.env.clusters[0]
        self.task = Task(cluster_id=self.env.clusters[0].id)
        self.env.db.add(self.task)
        self.env.db.commit()

    def set_node_status(self, status):
        self.node.status = status
        self.env.db.commit()
        self.assertEqual(self.node.status, status)

    def set_node_error_type(self, error_type):
        self.node.error_type = error_type
        self.env.db.commit()
        self.assertEqual(self.node.error_type, error_type)

    def is_checking_required(self):
        return task.CheckBeforeDeploymentTask._is_disk_checking_required(
            self.node)

    def test_is_disk_checking_required(self):
        self.set_node_status('ready')
        self.assertFalse(self.is_checking_required())

        self.set_node_status('deploying')
        self.assertFalse(self.is_checking_required())

        self.set_node_status('discover')
        self.assertTrue(self.is_checking_required())

        self.set_node_status('provisioned')
        self.assertFalse(self.is_checking_required())

    def test_is_disk_checking_required_in_case_of_error(self):
        self.set_node_status('error')
        self.set_node_error_type('provision')
        self.assertTrue(self.is_checking_required())

        self.set_node_error_type('deploy')
        self.assertFalse(self.is_checking_required())

    def test_check_volumes_and_disks_do_not_run_if_node_ready(self):
        self.set_node_status('ready')

        with mock.patch.object(
                VolumeManager,
                'check_disk_space_for_deployment') as check_mock:
            task.CheckBeforeDeploymentTask._check_disks(self.task)
            self.assertFalse(check_mock.called)

        with mock.patch.object(
                VolumeManager,
                'check_volume_sizes_for_deployment') as check_mock:
            task.CheckBeforeDeploymentTask._check_volumes(self.task)
            self.assertFalse(check_mock.called)

    def test_check_volumes_and_disks_run_if_node_not_ready(self):
        self.set_node_status('discover')

        with mock.patch.object(
                VolumeManager,
                'check_disk_space_for_deployment') as check_mock:
            task.CheckBeforeDeploymentTask._check_disks(self.task)

            self.assertEqual(check_mock.call_count, 1)

        with mock.patch.object(
                VolumeManager,
                'check_volume_sizes_for_deployment') as check_mock:
            task.CheckBeforeDeploymentTask._check_volumes(self.task)

            self.assertEqual(check_mock.call_count, 1)

    def test_check_nodes_online_raises_exception(self):
        self.node.online = False
        self.env.db.commit()

        self.assertRaises(
            errors.NodeOffline,
            task.CheckBeforeDeploymentTask._check_nodes_are_online,
            self.task)

    def test_check_nodes_online_do_not_raise_exception_node_to_deletion(self):
        self.node.online = False
        self.node.pending_deletion = True
        self.env.db.commit()

        task.CheckBeforeDeploymentTask._check_nodes_are_online(self.task)

    def find_net_by_name(self, nets, name):
        for net in nets['networks']:
            if net['name'] == name:
                return net

    def test_missing_network_group_with_template(self):
        net_template = self.env.read_fixtures(['network_template_80'])[0]
        objects.Cluster.set_network_template(
            self.cluster,
            net_template
        )
        public = [n for n in self.cluster.network_groups
                  if n.name == consts.NETWORKS.public][0]
        self.env._delete_network_group(public.id)

        self.assertRaisesRegexp(
            errors.NetworkTemplateMissingNetworkGroup,
            "The following network groups are missing: public",
            task.CheckBeforeDeploymentTask._validate_network_template,
            self.task)

    def test_missing_node_role_from_template(self):
        net_template = self.env.read_fixtures(['network_template_80'])[0]
        objects.Cluster.set_network_template(
            self.cluster,
            net_template
        )
        cluster_assigned_roles = \
            objects.Cluster.get_assigned_roles(self.cluster)

        conf_template = self.cluster.network_config.configuration_template

        for net_group in six.itervalues(conf_template['adv_net_template']):
            template_node_roles = net_group['templates_for_node_role']
            for assigned_role in cluster_assigned_roles:
                if assigned_role in template_node_roles:
                    del template_node_roles[assigned_role]

        self.assertRaises(
            errors.NetworkTemplateMissingRoles,
            task.CheckBeforeDeploymentTask._validate_network_template,
            self.task
        )

    def test_missing_network_group_with_template_multi_ng(self):
        net_template = self.env.read_fixtures(['network_template_80'])[0]
        resp = self.env.create_node_group(name='group-custom-1',
                                          cluster_id=self.cluster.id)
        del self.cluster.nodes[0]
        ng = objects.NodeGroup.get_by_uid(resp.json_body['id'])
        self.env.create_nodes_w_interfaces_count(
            1, 5,
            roles=['controller'],
            cluster_id=self.cluster.id,
            group_id=ng.id
        )
        objects.Cluster.set_network_template(
            self.cluster,
            net_template
        )
        public = [n for n in ng.networks
                  if n.name == consts.NETWORKS.public][0]
        self.env._delete_network_group(public.id)

        self.assertRaisesRegexp(
            errors.NetworkTemplateMissingNetworkGroup,
            ("The following network groups are missing: public "
             ".* group-custom-1"),
            task.CheckBeforeDeploymentTask._validate_network_template,
            self.task)

    def test_default_net_data_used_for_checking_absent_node_groups(self):
        self.env.create_node_group(api=False, name='new_group',
                                   cluster_id=self.cluster.id)

        # template validation should pass without errors
        # as the 'default' sub-template must be used for 'new_group'
        # (same as for 'default' node group)
        self.assertNotRaises(
            Exception,
            task.CheckBeforeDeploymentTask._validate_network_template,
            self.task
        )

    def test_check_public_networks(self):
        cluster = self.env.clusters[0]
        self.env.create_nodes(
            2, api=True, roles=['controller'], cluster_id=cluster.id)
        self.env.create_nodes(
            2, api=True, roles=['compute'], cluster_id=cluster.id)
        # we have 3 controllers now
        self.assertEqual(
            sum('controller' in n.all_roles for n in self.env.nodes),
            3
        )

        attrs = cluster.attributes.editable
        self.assertEqual(
            attrs['public_network_assignment']['assign_to_all_nodes']['value'],
            False
        )
        self.assertFalse(
            objects.Cluster.should_assign_public_to_all_nodes(cluster))

        resp = self.env.neutron_networks_get(cluster.id)
        nets = resp.json_body

        # not enough IPs for 3 nodes and 2 VIPs
        self.find_net_by_name(nets, 'public')['ip_ranges'] = \
            [["172.16.0.2", "172.16.0.5"]]
        resp = self.env.neutron_networks_put(cluster.id, nets)
        self.assertEqual(resp.status_code, 200)

        self.assertRaises(
            errors.NetworkCheckError,
            task.CheckBeforeDeploymentTask._check_public_network,
            self.task)

        # enough IPs for 3 nodes and 2 VIPs
        self.find_net_by_name(nets, 'public')['ip_ranges'] = \
            [["172.16.0.2", "172.16.0.6"]]
        resp = self.env.neutron_networks_put(cluster.id, nets)
        self.assertEqual(resp.status_code, 200)

        self.assertNotRaises(
            errors.NetworkCheckError,
            task.CheckBeforeDeploymentTask._check_public_network,
            self.task)

        attrs['public_network_assignment']['assign_to_all_nodes']['value'] = \
            True
        resp = self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster.id}),
            params=jsonutils.dumps({'editable': attrs}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertTrue(
            objects.Cluster.should_assign_public_to_all_nodes(cluster))

        self.assertRaises(
            errors.NetworkCheckError,
            task.CheckBeforeDeploymentTask._check_public_network,
            self.task)

    def test_check_deployment_graph_with_correct_data(self):
        correct_yaml_tasks = """
        - id: test-controller
          type: group
          role: [test-controller]
          requires: [primary-controller]
          required_for: [deploy_end]
          parameters:
            strategy:
              type: parallel
              amount: 2
        """
        tasks = yaml.load(correct_yaml_tasks)
        deployment_tasks = objects.Cluster.get_deployment_tasks(self.cluster)
        deployment_tasks.extend(tasks)
        objects.Cluster.update(
            self.cluster,
            {'deployment_tasks': deployment_tasks})
        task.CheckBeforeDeploymentTask.\
            _check_deployment_graph_for_correctness(
                self.task)

    def test_check_deployment_graph_with_incorrect_dependencies_data(self):
        incorrect_dependencies_yaml_tasks = """
        - id: test-controller
          type: group
          role: [primary-controller]
          required_for: [non_existing_stage]
          parameters:
            strategy:
              type: one_by_one
        """
        tasks = yaml.load(incorrect_dependencies_yaml_tasks)
        deployment_tasks = objects.Cluster.get_deployment_tasks(self.cluster)
        deployment_tasks.extend(tasks)
        objects.Cluster.update(
            self.cluster,
            {'deployment_tasks': deployment_tasks})
        with self.assertRaisesRegexp(
                errors.InvalidData,
                "Tasks 'non_existing_stage' can't be in requires|required_for|"
                "groups|tasks for \['test-controller'\] because they don't "
                "exist in the graph"):
            task.CheckBeforeDeploymentTask.\
                _check_deployment_graph_for_correctness(
                    self.task)

    def test_check_deployment_graph_with_cycling_dependencies_data(self):
        incorrect_cycle_yaml_tasks = """
        - id: test-controller-1
          type: role
          requires: [test-controller-2]
        - id: test-controller-2
          type: role
          requires: [test-controller-1]
        """
        tasks = yaml.load(incorrect_cycle_yaml_tasks)
        deployment_tasks = objects.Cluster.get_deployment_tasks(self.cluster)
        deployment_tasks.extend(tasks)
        objects.Cluster.update(
            self.cluster,
            {'deployment_tasks': deployment_tasks})
        with self.assertRaisesRegexp(
                errors.InvalidData,
                "Tasks can not be processed because it contains cycles in it"):
            task.CheckBeforeDeploymentTask.\
                _check_deployment_graph_for_correctness(
                    self.task)

    def test_check_missed_nodes_vmware_nova_computes(self):
        operational_node = self.env.create_node(
            roles=['compute-vmware'],
            cluster_id=self.cluster.id,
            name='node-1'
        )
        pending_addition_node = self.env.create_node(
            roles=['compute-vmware'],
            cluster_id=self.cluster.id,
            pending_addition=True,
            name='node-2'
        )
        msg = ("The following compute-vmware nodes are not assigned to "
               "any vCenter cluster: {0}").format(', '.join(
                   sorted([operational_node.name, pending_addition_node.name])
               ))
        with self.assertRaisesRegexp(errors.CheckBeforeDeploymentError, msg):
            task.CheckBeforeDeploymentTask._check_vmware_consistency(self.task)

    @mock.patch('objects.VmwareAttributes.get_nova_computes_target_nodes')
    def test_check_not_deleted_nodes_vmware_nova_computes(self, target_nodes):
        operational_node = self.env.create_node(
            roles=['compute-vmware'],
            cluster_id=self.cluster.id,
            name='node-1'
        )
        pending_deletion_node = self.env.create_node(
            roles=['compute-vmware'],
            cluster_id=self.cluster.id,
            pending_deletion=True,
            name='node-2'
        )
        target_nodes.return_value = [{
            'id': operational_node.hostname,
            'label': operational_node.name
        }, {
            'id': pending_deletion_node.hostname,
            'label': pending_deletion_node.name
        }]
        msg = ("The following nodes are prepared for deletion and couldn't be "
               "assigned to any vCenter cluster: {0}".format(
                   pending_deletion_node.name))
        with self.assertRaisesRegexp(errors.CheckBeforeDeploymentError, msg):
            task.CheckBeforeDeploymentTask._check_vmware_consistency(self.task)

    @mock.patch('objects.VmwareAttributes.get_nova_computes_target_nodes')
    def test_check_extra_nodes_vmware_nova_computes(self, target_nodes):
        operational_node = self.env.create_node(
            roles=['compute-vmware'],
            cluster_id=self.cluster.id,
            name='node-1'
        )
        non_cluster_node = self.env.create_node(
            roles=['compute-vmware'],
            name='node-2'
        )
        other_role_node = self.env.create_node(
            cluster_id=self.cluster.id,
            name='node-3'
        )
        target_nodes.return_value = [{
            'id': operational_node.hostname,
            'label': operational_node.name
        }, {
            'id': non_cluster_node.hostname,
            'label': non_cluster_node.name
        }, {
            'id': other_role_node.hostname,
            'label': other_role_node.name
        }]
        msg = ("The following nodes don't belong to compute-vmware nodes of "
               "environment and couldn't be assigned to any vSphere cluster: "
               "{0}".format(', '.join(
                   sorted([non_cluster_node.name, other_role_node.name]))
               ))
        with self.assertRaisesRegexp(errors.CheckBeforeDeploymentError, msg):
            task.CheckBeforeDeploymentTask._check_vmware_consistency(self.task)


class TestDeployTask(base.BaseTestCase):

    def create_deploy_tasks(self):
        self.env.create()
        cluster = self.env.clusters[0]

        deploy_task = Task(name=consts.TASK_NAMES.deploy,
                           cluster_id=cluster.id,
                           status=consts.TASK_STATUSES.pending)
        self.db.add(deploy_task)
        self.db.flush()
        provision_task = Task(name=consts.TASK_NAMES.provision,
                              status=consts.TASK_STATUSES.pending,
                              parent_id=deploy_task.id, cluster_id=cluster.id)
        self.db.add(provision_task)
        deployment_task = Task(name=consts.TASK_NAMES.deployment,
                               status=consts.TASK_STATUSES.pending,
                               parent_id=deploy_task.id, cluster_id=cluster.id)
        self.db.add(deployment_task)
        self.db.flush()

        return deploy_task, provision_task, deployment_task

    def test_running_status_bubble_for_deploy_task(self):
        deploy_task, provision_task, deployment_task = \
            self.create_deploy_tasks()

        objects.Task.update(provision_task,
                            {'status': consts.TASK_STATUSES.running})

        # Only deploy and provision tasks are running now
        self.assertEqual(consts.TASK_STATUSES.running, deploy_task.status)
        self.assertEqual(consts.TASK_STATUSES.running, provision_task.status)
        self.assertEqual(consts.TASK_STATUSES.pending, deployment_task.status)

    def test_error_status_bubble_for_deploy_task(self):
        deploy_task, provision_task, deployment_task = \
            self.create_deploy_tasks()

        objects.Task.update(provision_task,
                            {'status': consts.TASK_STATUSES.error})

        # All tasks have error status
        self.assertEqual(consts.TASK_STATUSES.error, deploy_task.status)
        self.assertEqual(consts.TASK_STATUSES.error, provision_task.status)
        self.assertEqual(consts.TASK_STATUSES.error, deployment_task.status)

    def test_ready_status_bubble_for_deploy_task(self):
        deploy_task, provision_task, deployment_task = \
            self.create_deploy_tasks()

        objects.Task.update(provision_task,
                            {'status': consts.TASK_STATUSES.ready})

        # Not all child bugs in ready state
        self.assertEqual(consts.TASK_STATUSES.running, deploy_task.status)
        self.assertEqual(consts.TASK_STATUSES.ready, provision_task.status)
        self.assertEqual(consts.TASK_STATUSES.pending, deployment_task.status)

        # All child bugs in ready state
        objects.Task.update(deployment_task,
                            {'status': consts.TASK_STATUSES.ready})
        self.assertEqual(consts.TASK_STATUSES.ready, deploy_task.status)
        self.assertEqual(consts.TASK_STATUSES.ready, provision_task.status)
        self.assertEqual(consts.TASK_STATUSES.ready, deployment_task.status)
