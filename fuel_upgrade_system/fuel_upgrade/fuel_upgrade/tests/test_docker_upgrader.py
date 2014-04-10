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

import mock

from fuel_upgrade import errors
from fuel_upgrade.tests.base import BaseTestCase
from fuel_upgrade.upgrade import DockerUpgrader


@mock.patch('fuel_upgrade.upgrade.utils.exec_cmd')
class TestDockerUpgrader(BaseTestCase):

    def setUp(self):
        # NOTE (eli): mocking doesn't work correctly
        # when we try to patch docker client with
        # class decorator, it's the reason why
        # we have to do it explicitly
        self.docker_patcher = mock.patch('fuel_upgrade.upgrade.Client')
        self.docker_mock_class = self.docker_patcher.start()
        self.docker_mock = mock.MagicMock()
        self.docker_mock_class.return_value = self.docker_mock

        self.supervisor_patcher = mock.patch(
            'fuel_upgrade.upgrade.SupervisorClient')
        self.supervisor_class = self.supervisor_patcher.start()
        self.supervisor_mock = mock.MagicMock()
        self.supervisor_class.return_value = self.supervisor_mock

        self.update_path = '/tmp/new_update'
        with mock.patch('os.makedirs'):
            self.upgrader = DockerUpgrader(
                self.update_path, self.fake_config)

    def tearDown(self):
        self.docker_patcher.stop()
        self.supervisor_patcher.stop()

    @mock.patch('fuel_upgrade.upgrade.time.sleep')
    def test_run_with_retries(self, sleep, _):
        image_name = 'test_image'
        retries_count = 3

        with self.assertRaises(errors.DockerExecutedErrorNonZeroExitCode):
            self.upgrader.run(
                image_name,
                retry_interval=1,
                retries_count=retries_count)

        self.assertEquals(sleep.call_count, retries_count)
        self.called_once(self.docker_mock.create_container)

    def test_run_without_errors(self, exec_cmd):
        image_name = 'test_image'
        self.docker_mock.wait.return_value = 0

        self.upgrader.run(image_name)

        self.called_once(self.docker_mock.create_container)
        self.called_once(self.docker_mock.logs)
        self.called_once(self.docker_mock.start)
        self.called_once(self.docker_mock.wait)

    def mock_methods(self, obj, methods):
        for method in methods:
            setattr(obj, method, mock.MagicMock())

    def test_upgrade(self, _):
        mocked_methods = [
            'stop_fuel_containers',
            'upload_images',
            'run_post_build_actions',
            'create_containers',
            'generate_configs',
            'switch_to_new_configs']

        self.mock_methods(self.upgrader, mocked_methods)
        self.upgrader.upgrade()

        # Check that all methods was called once
        # except stop_fuel_containers method
        for method in mocked_methods[1:-1]:
            self.called_once(getattr(self.upgrader, method))

        self.called_times(self.upgrader.stop_fuel_containers, 3)

        self.called_once(self.supervisor_mock.stop_all_services)
        self.called_once(self.supervisor_mock.restart_and_wait)

    def test_rollback(self, _):
        self.upgrader.stop_fuel_containers = mock.MagicMock()
        self.upgrader.rollback()

        self.called_times(self.upgrader.stop_fuel_containers, 1)
        self.called_once(self.supervisor_mock.switch_to_previous_configs)
        self.called_once(self.supervisor_mock.stop_all_services)
        self.called_once(self.supervisor_mock.restart_and_wait)

    def test_stop_fuel_containers(self, _):
        non_fuel_images = [
            'first_image_1.0', 'second_image_2.0', 'third_image_2.0']
        fuel_images = [
            'fuel/image_1.0', 'fuel/image_2.0']

        all_images = [{'Image': v, 'Id': i}
                      for i, v in enumerate(non_fuel_images + fuel_images)]

        self.docker_mock.containers.return_value = all_images
        self.upgrader.stop_fuel_containers()
        self.assertEquals(
            self.docker_mock.stop.call_args_list, [((3, 10),), ((4, 10),)])

    @mock.patch('fuel_upgrade.upgrade.os.path.exists', return_value=True)
    def test_upload_images(self, _, exec_mock):
        self.upgrader.new_release_images = [
            {'docker_image': 'image1'},
            {'docker_image': 'image2'}]

        self.upgrader.upload_images()
        self.assertEquals(
            exec_mock.call_args_list,
            [(('docker load < "image1"',),),
             (('docker load < "image2"',),)])

    def test_create_containers(self, _):
        self.upgrader.new_release_containers = [
            {'id': 'id1',
             'container_name': 'name1',
             'image_name': 'i_name1',
             'volumes_from': ['id2']},
            {'id': 'id2',
             'image_name': 'i_name2',
             'container_name': 'name2'}]

        def mocked_create_container(*args, **kwargs):
            """Return name of the container
            """
            return kwargs['name']

        self.upgrader.create_container = mock.MagicMock(
            side_effect=mocked_create_container)
        self.upgrader.start_container = mock.MagicMock()

        self.upgrader.create_containers()

        create_container_calls = [
            (('i_name2',), {'detach': False, 'ports': None,
                            'volumes': None, 'name': 'name2'}),
            (('i_name1',), {'detach': False, 'ports': None,
                            'volumes': None, 'name': 'name1'})]

        start_container_calls = [
            (('name2',), {'volumes_from': [],
                          'binds': None, 'port_bindings': None,
                          'privileged': False, 'links': []}),
            (('name1',), {'volumes_from': ['name2'],
                          'binds': None, 'port_bindings': None,
                          'privileged': False, 'links': []})]

        self.assertEquals(
            self.upgrader.create_container.call_args_list,
            create_container_calls)
        self.assertEquals(
            self.upgrader.start_container.call_args_list,
            start_container_calls)

    def test_create_container(self, _):
        self.upgrader.create_container(
            'image_name', param1=1, param2=2, ports=[1234])

        self.docker_mock.create_container.assert_called_once_with(
            'image_name', param2=2, param1=1, ports=[1234])

    def test_start_container(self, _):
        self.upgrader.start_container(
            {'Id': 'container_id'}, param1=1, param2=2)

        self.docker_mock.start.assert_called_once_with(
            'container_id', param2=2, param1=1)

    def test_build_dependencies_graph(self, _):
        containers = [
            {'id': '1', 'volumes_from': ['2'], 'links': [{'id': '3'}]},
            {'id': '2', 'volumes_from': [], 'links': []},
            {'id': '3', 'volumes_from': [], 'links': [{'id': '2'}]}]

        actual_graph = self.upgrader.build_dependencies_graph(containers)
        expected_graph = {
            '1': ['3', '2'],
            '2': [],
            '3': ['2']}

        self.assertEquals(actual_graph, expected_graph)

    def test_get_container_links(self, _):
        fake_containers = [
            {'id': 'id1', 'container_name': 'container_name1',
             'links': [{'id': 'id2', 'alias': 'alias2'}]},
            {'id': 'id2', 'container_name': 'container_name2'}]
        self.upgrader.new_release_containers = fake_containers
        links = self.upgrader.get_container_links(fake_containers[0])
        self.assertEquals(links, [('container_name2', 'alias2')])

    def test_get_port_bindings(self, _):
        port_bindings = {'port_bindings': {'53/udp': ['0.0.0.0', 53]}}
        bindings = self.upgrader.get_port_bindings(port_bindings)
        self.assertEquals({'53/udp': ('0.0.0.0', 53)}, bindings)

    def test_get_ports(self, _):
        ports = self.upgrader.get_ports({'ports': [[53, 'udp'], 100]})
        self.assertEquals([(53, 'udp'), 100], ports)

    def test_generate_configs(self, _):
        fake_containers = [
            {'id': 'id1', 'container_name': 'container_name1',
             'supervisor_config': False},
            {'id': 'id2', 'container_name': 'container_name2',
             'supervisor_config': True},
            {'id': 'cobbler', 'container_name': 'cobbler_container',
             'supervisor_config': False}]
        self.upgrader.new_release_containers = fake_containers
        self.upgrader.generate_configs()
        self.supervisor_mock.generate_configs.assert_called_once_with(
            [{'service_name': 'id2',
              'command': 'docker start -a container_name2'}])
        self.supervisor_mock.generate_cobbler_config.assert_called_once_with(
            {'service_name': 'cobbler', 'container_name': 'cobbler_container'})

    def test_switch_to_new_configs(self, _):
        self.upgrader.switch_to_new_configs()
        self.supervisor_mock.switch_to_new_configs.called_once()
