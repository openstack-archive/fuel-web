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

from fuel_upgrade.engines.docker_engine import DockerUpgrader
from fuel_upgrade import errors

from fuel_upgrade.tests.base import BaseTestCase


class TestDockerUpgrader(BaseTestCase):

    def setUp(self):
        # NOTE (eli): mocking doesn't work correctly
        # when we try to patch docker client with
        # class decorator, it's the reason why
        # we have to do it explicitly
        self.docker_patcher = mock.patch(
            'fuel_upgrade.engines.docker_engine.docker.Client')
        self.docker_mock_class = self.docker_patcher.start()
        self.docker_mock = mock.MagicMock()
        self.docker_mock_class.return_value = self.docker_mock

        self.supervisor_patcher = mock.patch(
            'fuel_upgrade.engines.docker_engine.SupervisorClient')
        self.supervisor_class = self.supervisor_patcher.start()
        self.supervisor_mock = mock.MagicMock()
        self.supervisor_class.return_value = self.supervisor_mock

        self.version_mock = mock.MagicMock()

        with mock.patch('fuel_upgrade.engines.docker_engine.utils'):
            with mock.patch('fuel_upgrade.engines.docker_engine.VersionFile',
                            return_value=self.version_mock):
                self.upgrader = DockerUpgrader(self.fake_config)
                self.upgrader.upgrade_verifier = mock.MagicMock()

        self.pg_dump_path = '/var/lib/fuel_upgrade/9999/pg_dump_all.sql'

    def tearDown(self):
        self.docker_patcher.stop()
        self.supervisor_patcher.stop()

    def mock_methods(self, obj, methods):
        for method in methods:
            setattr(obj, method, mock.MagicMock())

    def test_upgrade(self):
        mocked_methods = [
            'stop_fuel_containers',
            'save_db',
            'save_cobbler_configs',
            'upload_images',
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
        self.called_once(self.upgrader.upgrade_verifier.verify)
        self.called_once(self.version_mock.save_current)
        self.called_once(self.version_mock.switch_to_new)

    def test_rollback(self):
        self.upgrader.stop_fuel_containers = mock.MagicMock()
        self.upgrader.switch_version_file_to_previous_version = \
            mock.MagicMock()
        self.upgrader.rollback()

        self.called_times(self.upgrader.stop_fuel_containers, 1)
        self.called_once(self.supervisor_mock.switch_to_previous_configs)
        self.called_once(self.supervisor_mock.stop_all_services)
        self.called_once(self.supervisor_mock.restart_and_wait)
        self.called_once(self.version_mock.save_current)
        self.called_once(self.version_mock.switch_to_previous)

    @mock.patch('fuel_upgrade.engines.docker_engine.utils')
    @mock.patch('fuel_upgrade.engines.docker_engine.glob.glob',
                return_value=['file1', 'file2'])
    def test_on_success(self, glob_mock, utils_mock):
        self.upgrader.on_success()
        glob_mock.assert_called_once_with(self.fake_config.version_files_mask)
        self.assertEqual(
            utils_mock.remove.call_args_list,
            [mock.call('file1'), mock.call('file2')])

    def test_stop_fuel_containers(self):
        non_fuel_images = [
            'first_image_1.0', 'second_image_2.0', 'third_image_2.0']
        fuel_images = [
            'fuel/image_1.0', 'fuel/image_2.0']

        all_images = [{'Image': v, 'Id': i}
                      for i, v in enumerate(non_fuel_images + fuel_images)]

        ports = [1, 2, 3]
        self.upgrader._get_docker_container_public_ports = mock.MagicMock(
            return_value=ports)
        self.docker_mock.containers.return_value = all_images
        self.upgrader.stop_fuel_containers()
        self.assertEqual(
            self.docker_mock.stop.call_args_list,
            [mock.call(3, 10), mock.call(4, 10)])

    @mock.patch('fuel_upgrade.engines.docker_engine.utils.exec_cmd')
    @mock.patch('fuel_upgrade.engines.docker_engine.os.path.exists',
                return_value=True)
    def test_upload_images(self, _, exec_mock):
        self.upgrader.new_release_images = [
            {'docker_image': 'image1'},
            {'docker_image': 'image2'}]

        self.upgrader.upload_images()
        self.assertEqual(
            exec_mock.call_args_list,
            [mock.call('docker load < "image1"'),
             mock.call('docker load < "image2"')])

    def test_create_containers(self):
        self.upgrader.new_release_containers = [
            {'id': 'id1',
             'container_name': 'name1',
             'image_name': 'i_name1',
             'volumes_from': ['id2']},
            {'id': 'id2',
             'image_name': 'i_name2',
             'container_name': 'name2',
             'after_container_creation_command': 'cmd'}]

        def mocked_create_container(*args, **kwargs):
            """Return name of the container
            """
            return kwargs['name']

        self.upgrader.create_container = mock.MagicMock(
            side_effect=mocked_create_container)
        self.upgrader.start_container = mock.MagicMock()
        self.upgrader.run_after_container_creation_command = mock.MagicMock()

        self.upgrader.create_containers()

        create_container_calls = [
            mock.call('i_name2', detach=False, ports=None,
                      volumes=None, name='name2'),
            mock.call('i_name1', detach=False, ports=None,
                      volumes=None, name='name1')]

        start_container_calls = [
            mock.call('name2', volumes_from=[],
                      binds=None, port_bindings=None,
                      privileged=False, links=[]),
            mock.call('name1', volumes_from=['name2'],
                      binds=None, port_bindings=None,
                      privileged=False, links=[])]

        self.assertEqual(
            self.upgrader.create_container.call_args_list,
            create_container_calls)
        self.assertEqual(
            self.upgrader.start_container.call_args_list,
            start_container_calls)
        self.called_once(self.upgrader.run_after_container_creation_command)

    def test_run_after_container_creation_command(self):
        self.upgrader.exec_with_retries = mock.MagicMock()
        self.upgrader.run_after_container_creation_command({
            'after_container_creation_command': 'cmd',
            'container_name': 'name'})

        args, kwargs = self.upgrader.exec_with_retries.call_args

        self.assertEqual(args[1], errors.ExecutedErrorNonZeroExitCode)
        self.assertEqual(kwargs, {'retries': 30, 'interval': 4})

    def test_create_container(self):
        self.upgrader.create_container(
            'image_name', param1=1, param2=2, ports=[1234])

        self.docker_mock.create_container.assert_called_once_with(
            'image_name', param2=2, param1=1, ports=[1234])

    def test_start_container(self):
        self.upgrader.start_container(
            {'Id': 'container_id'}, param1=1, param2=2)

        self.docker_mock.start.assert_called_once_with(
            'container_id', param2=2, param1=1)

    def test_build_dependencies_graph(self):
        containers = [
            {'id': '1', 'volumes_from': ['2'], 'links': [{'id': '3'}]},
            {'id': '2', 'volumes_from': [], 'links': []},
            {'id': '3', 'volumes_from': [], 'links': [{'id': '2'}]}]

        actual_graph = self.upgrader.build_dependencies_graph(containers)
        expected_graph = {
            '1': ['2', '3'],
            '2': [],
            '3': ['2']}

        self.assertEqual(actual_graph, expected_graph)

    def test_get_container_links(self):
        fake_containers = [
            {'id': 'id1', 'container_name': 'container_name1',
             'links': [{'id': 'id2', 'alias': 'alias2'}]},
            {'id': 'id2', 'container_name': 'container_name2'}]
        self.upgrader.new_release_containers = fake_containers
        links = self.upgrader.get_container_links(fake_containers[0])
        self.assertEqual(links, [('container_name2', 'alias2')])

    def test_get_ports(self):
        ports = self.upgrader.get_ports({'ports': [[53, 'udp'], 100]})
        self.assertEqual([(53, 'udp'), 100], ports)

    def test_generate_configs(self):
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

    def test_switch_to_new_configs(self):
        self.upgrader.switch_to_new_configs()
        self.supervisor_mock.switch_to_new_configs.assert_called_once_with()

    @mock.patch('fuel_upgrade.engines.docker_engine.utils.exec_cmd')
    def test_exec_cmd_in_container(self, exec_cmd_mock):
        name = 'container_name'
        cmd = 'some command'

        self.upgrader.container_docker_id = mock.MagicMock(return_value=name)
        self.upgrader.exec_cmd_in_container(name, cmd)

        self.called_once(self.upgrader.container_docker_id)
        exec_cmd_mock.assert_called_once_with(
            "lxc-attach --name {0} -- {1}".format(name, cmd))

    @mock.patch('fuel_upgrade.engines.docker_engine.'
                'utils.exec_cmd')
    @mock.patch('fuel_upgrade.engines.docker_engine.'
                'DockerUpgrader.verify_cobbler_configs')
    def test_save_cobbler_configs(self, verify_mock, exec_cmd_mock):
        self.upgrader.save_cobbler_configs()

        exec_cmd_mock.assert_called_once_with(
            'docker cp fuel-core-0-cobbler:/var/lib/cobbler/config '
            '/var/lib/fuel_upgrade/9999/cobbler_configs')
        self.called_once(verify_mock)

    @mock.patch('fuel_upgrade.engines.docker_engine.utils.rmtree')
    @mock.patch('fuel_upgrade.engines.docker_engine.utils.exec_cmd',
                side_effect=errors.ExecutedErrorNonZeroExitCode())
    def test_save_cobbler_configs_removes_dir_in_case_of_error(
            self, exec_cmd_mock, rm_mock):

        with self.assertRaises(errors.ExecutedErrorNonZeroExitCode):
            self.upgrader.save_cobbler_configs()

        cobbler_config_path = '/var/lib/fuel_upgrade/9999/cobbler_configs'
        exec_cmd_mock.assert_called_once_with(
            'docker cp fuel-core-0-cobbler:/var/lib/cobbler/config '
            '{0}'.format(cobbler_config_path))
        rm_mock.assert_called_once_with(cobbler_config_path)

    @mock.patch('fuel_upgrade.engines.docker_engine.glob.glob',
                return_value=['1.json'])
    @mock.patch('fuel_upgrade.engines.docker_engine.utils.'
                'check_file_is_valid_json')
    def test_verify_cobbler_configs(self, json_checker_mock, glob_mock):
        self.upgrader.verify_cobbler_configs()
        glob_mock.assert_called_once_with(
            '/var/lib/fuel_upgrade/9999/'
            'cobbler_configs/config/systems.d/*.json')
        json_checker_mock.assert_called_once_with('1.json')

    @mock.patch('fuel_upgrade.engines.docker_engine.glob.glob',
                return_value=[])
    def test_verify_cobbler_configs_raises_error_if_not_enough_systems(
            self, glob_mock):

        with self.assertRaises(errors.WrongCobblerConfigsError):
            self.upgrader.verify_cobbler_configs()
        self.called_once(glob_mock)

    @mock.patch('fuel_upgrade.engines.docker_engine.glob.glob',
                return_value=['1.json'])
    @mock.patch('fuel_upgrade.engines.docker_engine.utils.'
                'check_file_is_valid_json', return_value=False)
    def test_verify_cobbler_configs_raises_error_if_invalid_file(
            self, json_checker_mock, glob_mock):

        with self.assertRaises(errors.WrongCobblerConfigsError):
            self.upgrader.verify_cobbler_configs()

        self.called_once(glob_mock)
        self.called_once(json_checker_mock)

    def test_get_docker_container_public_ports(self):
        docker_ports_mapping = [
            {'Ports': [
                {'PublicPort': 514},
                {'PublicPort': 515}]},
            {'Ports': [
                {'PublicPort': 516},
                {'PublicPort': 517}]}]

        self.assertEquals(
            [514, 515, 516, 517],
            self.upgrader._get_docker_container_public_ports(
                docker_ports_mapping))

    @mock.patch('fuel_upgrade.engines.docker_engine.utils.safe_exec_cmd')
    def test_clean_docker_iptables_rules(self, exec_cmd_mock):
        container = {'id': 'astute'}
        self.upgrader.clean_docker_iptables_rules(container)
        exec_cmd_mock.assert_called_once_with(
            'dockerctl post_start_hooks astute')

    @mock.patch('fuel_upgrade.engines.docker_engine.utils.files_size',
                return_value=5)
    def test_required_free_space(self, _):
        self.assertEqual(
            self.upgrader.required_free_space,
            {'/var/lib/fuel_upgrade/9999': 150,
             '/var/lib/docker': 5,
             '/etc/fuel/': 10,
             '/etc/supervisord.d/': 10})

    @mock.patch('fuel_upgrade.engines.docker_engine.'
                'DockerUpgrader.exec_cmd_in_container')
    @mock.patch('fuel_upgrade.engines.docker_engine.utils')
    def test_save_db_succeed(self, mock_utils, exec_cmd_mock):
        with mock.patch('fuel_upgrade.engines.docker_engine.'
                        'utils.VersionedFile') as version_mock:
            version_mock.return_value.sorted_files.return_value = [
                'file1', 'file2']
            version_mock.return_value.next_file_name.return_value = 'file3'

            self.upgrader.save_db()

        exec_cmd_mock.assert_called_once_with(
            'fuel-core-0-postgres',
            "su postgres -c 'pg_dumpall --clean' > file3")
        mock_utils.hardlink.assert_called_once_with(
            'file1', self.pg_dump_path, overwrite=True)

    @mock.patch('fuel_upgrade.engines.docker_engine.'
                'DockerUpgrader.exec_cmd_in_container',
                side_effect=errors.ExecutedErrorNonZeroExitCode())
    @mock.patch('fuel_upgrade.engines.docker_engine.utils')
    def test_save_db_error_failed_to_execute_dump_command(self, mock_utils, _):
        mock_utils.file_exists.return_value = False
        self.assertRaises(
            errors.ExecutedErrorNonZeroExitCode,
            self.upgrader.save_db)
        mock_utils.file_exists.assert_called_once_with(self.pg_dump_path)
        self.called_once(mock_utils.remove_if_exists)

    @mock.patch('fuel_upgrade.engines.docker_engine.'
                'DockerUpgrader.exec_cmd_in_container',
                side_effect=errors.CannotFindContainerError())
    @mock.patch('fuel_upgrade.engines.docker_engine.utils')
    def test_save_db_error_failed_because_of_stopped_container(
            self, mock_utils, exec_cmd_mock):
        mock_utils.file_exists.return_value = False
        self.assertRaises(
            errors.CannotFindContainerError,
            self.upgrader.save_db)
        mock_utils.file_exists.assert_called_once_with(self.pg_dump_path)
        self.called_once(mock_utils.remove_if_exists)

    @mock.patch('fuel_upgrade.engines.docker_engine.'
                'DockerUpgrader.exec_cmd_in_container')
    @mock.patch('fuel_upgrade.engines.docker_engine.utils')
    def test_save_db_error_first_dump_is_invalid(self, mock_utils, _):
        with mock.patch('fuel_upgrade.engines.docker_engine.'
                        'utils.VersionedFile') as version_mock:
            version_mock.return_value.filter_files.return_value = []
            self.assertRaises(errors.DatabaseDumpError, self.upgrader.save_db)

        self.method_was_not_called(mock_utils.hardlink)

    @mock.patch('fuel_upgrade.engines.docker_engine.'
                'DockerUpgrader.exec_cmd_in_container',
                side_effect=errors.ExecutedErrorNonZeroExitCode())
    @mock.patch('fuel_upgrade.engines.docker_engine.utils')
    def test_save_db_second_run_failed_to_execute_dump_command(
            self, mock_utils, exec_cmd_mock):
        mock_utils.file_exists.return_value = True

        with mock.patch('fuel_upgrade.engines.docker_engine.'
                        'utils.VersionedFile') as version_mock:
            version_mock.return_value.sorted_files.return_value = [
                'file1', 'file2']

            self.upgrader.save_db()

        mock_utils.file_exists.assert_called_once_with(self.pg_dump_path)
        self.called_once(mock_utils.remove_if_exists)
        self.called_once(mock_utils.hardlink)

    @mock.patch('fuel_upgrade.engines.docker_engine.'
                'DockerUpgrader.exec_cmd_in_container',
                side_effect=errors.CannotFindContainerError())
    @mock.patch('fuel_upgrade.engines.docker_engine.utils')
    def test_save_db_second_run_failed_failed_because_of_stopped_container(
            self, mock_utils, _):
        mock_utils.file_exists.return_value = True
        with mock.patch('fuel_upgrade.engines.docker_engine.'
                        'utils.VersionedFile') as version_mock:
            version_mock.return_value.sorted_files.return_value = ['file1']
            self.upgrader.save_db()

    @mock.patch('fuel_upgrade.engines.docker_engine.'
                'DockerUpgrader.exec_cmd_in_container')
    @mock.patch('fuel_upgrade.engines.docker_engine.utils')
    def test_save_db_removes_old_dump_files(self, mock_utils, _):
        mock_utils.file_exists.return_value = True
        with mock.patch('fuel_upgrade.engines.docker_engine.'
                        'utils.VersionedFile') as version_mock:
            version_mock.return_value.sorted_files.return_value = [
                'file1', 'file2', 'file3', 'file4', 'file5']
            self.upgrader.save_db()

        self.assertEqual(
            mock_utils.remove_if_exists.call_args_list,
            [mock.call('file4'), mock.call('file5')])
