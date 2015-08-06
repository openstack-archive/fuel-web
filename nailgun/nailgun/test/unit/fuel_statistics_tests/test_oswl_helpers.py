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

from mock import Mock
import six

from nailgun.test.base import BaseTestCase

from nailgun import consts
from nailgun.statistics.oswl import helpers


class TestOSWLHelpers(BaseTestCase):

    components_to_mock = {
        "nova": {
            "servers": [
                {
                    "id": 1,
                    "status": "running",
                    "OS-EXT-STS:power_state": 1,
                    "created": "date_of_creation",
                    "hostId": "test_host_id",
                    "tenant_id": "test_tenant_id",
                    "image": {"id": "test_image_id"},
                    "flavor": {"id": "test_flavor_id"},
                },
            ],
            "flavors": [
                {
                    "id": 2,
                    "ram": 64,
                    "vcpus": 4,
                    "OS-FLV-EXT-DATA:ephemeral": 1,
                    "disk": 1,
                    "swap": 16,
                },
            ],
            "images": [
                {
                    "id": 4,
                    "minDisk": 1,
                    "minRam": 64,
                    "OS-EXT-IMG-SIZE:size": 13000000,
                    "created": "some_date_of_creation",
                    "updated": "some_date_of_update"
                },
            ],
            "client": {"version": "v1.1"}
        },
        "cinder": {
            "volumes": [
                {
                    "id": 3,
                    "availability_zone": "test_availability_zone",
                    "encrypted": False,
                    "bootable": False,
                    "status": "available",
                    "volume_type": "test_volume",
                    "size": 1,
                    "snapshot_id": None,
                    "attachments": [
                        {
                            "device": "/dev/sda1",
                            "server_id": "one_test_server_id",
                            "id": "firs_test_id",
                            "host_name": "test_host",
                            "volume_id": "first_test_id",
                        },
                        {
                            "device": "/dev/sda2",
                            "server_id": "another_test_server_id",
                            "id": "second_test_id",
                            "host_name": "test_host",
                            "volume_id": "second_test_id",
                        },
                    ],
                    "os-vol-tenant-attr:tenant_id": "test_tenant",
                },
            ],
            "client": {"version": "v1"}
        },
        "keystone": {
            "tenants": [
                {
                    "id": 5,
                    "enabled": True,
                },
            ],
            "users": [
                {
                    "id": "test_user_id",
                    "enabled": True,
                    "tenantId": "test_tenant_id",
                }
            ],
            "version": "v2.0"
        },
    }

    def _prepare_client_provider_mock(self):
        client_provider_mock = Mock()

        clients_version_attr_path = {
            "nova": ["client", "version"],
            "cinder": ["client", "version"],
            "keystone": ["version"]
        }
        setattr(client_provider_mock, "clients_version_attr_path",
                clients_version_attr_path)

        return client_provider_mock

    def _update_mock_with_complex_dict(self, root_mock, attrs_dict):
        for key, value in six.iteritems(attrs_dict):
            attr_name = key
            attr_value = value

            if isinstance(value, dict):
                attr_value = Mock()
                self._update_mock_with_complex_dict(
                    attr_value, value
                )
            elif isinstance(value, list):
                attr_value = Mock()

                to_return = []
                for data in value:
                    attr_value_element = Mock()
                    attr_value_element.to_dict.return_value = data

                    to_return.append(attr_value_element)

                attr_value.list.return_value = to_return

            setattr(root_mock, attr_name, attr_value)

    def test_get_oswl_info(self):
        expected = {
            "vm": [
                {
                    "id": 1,
                    "status": "running",
                    "power_state": 1,
                    "created_at": "date_of_creation",
                    "image_id": "test_image_id",
                    "flavor_id": "test_flavor_id",
                    "host_id": "test_host_id",
                    "tenant_id": "test_tenant_id",
                },
            ],
            "flavor": [
                {
                    "id": 2,
                    "ram": 64,
                    "vcpus": 4,
                    "ephemeral": 1,
                    "disk": 1,
                    "swap": 16,
                },
            ],
            "image": [
                {
                    "id": 4,
                    "minDisk": 1,
                    "minRam": 64,
                    "sizeBytes": 13000000,
                    "created_at": "some_date_of_creation",
                    "updated_at": "some_date_of_update"
                },
            ],
            "volume": [
                {
                    "id": 3,
                    "availability_zone": "test_availability_zone",
                    "encrypted_flag": False,
                    "bootable_flag": False,
                    "status": "available",
                    "volume_type": "test_volume",
                    "size": 1,
                    "snapshot_id": None,
                    "attachments": [
                        {
                            "device": "/dev/sda1",
                            "server_id": "one_test_server_id",
                            "id": "firs_test_id",
                        },
                        {
                            "device": "/dev/sda2",
                            "server_id": "another_test_server_id",
                            "id": "second_test_id",
                        },
                    ],
                    "tenant_id": "test_tenant",
                },
            ],
            "tenant": [
                {
                    "id": 5,
                    "enabled_flag": True,
                },
            ],
            "keystone_user": [
                {
                    "id": "test_user_id",
                    "enabled_flag": True,
                    "tenant_id": "test_tenant_id",
                },
            ],
        }

        client_provider_mock = self._prepare_client_provider_mock()

        self._update_mock_with_complex_dict(client_provider_mock,
                                            self.components_to_mock)

        for resource_name, expected_data in six.iteritems(expected):
            actual = helpers.get_info_from_os_resource_manager(
                client_provider_mock, resource_name
            )
            self.assertEqual(actual, expected_data)

    def test_different_api_versions_handling_for_tenants(self):
        keystone_v2_component = {
            "keystone": {
                "tenants": [
                    {
                        "id": 5,
                        "enabled": True,
                    },
                ],
                "version": "v2.0"
            },
        }

        keystone_v3_component = {
            "keystone": {
                "projects": [
                    {
                        "id": 5,
                        "enabled": True,
                    },
                ],
                "version": "v3.0"
            },
        }

        client_provider_mock = self._prepare_client_provider_mock()
        self._update_mock_with_complex_dict(client_provider_mock,
                                            keystone_v2_component)
        client_provider_mock.keystone.tenants.list.assert_called_once()

        client_provider_mock = self._prepare_client_provider_mock()
        self._update_mock_with_complex_dict(client_provider_mock,
                                            keystone_v3_component)
        client_provider_mock.keystone.projects.list.assert_called_once()

    def test_different_api_versions_handling_for_users(self):
        keystone_v2_component = {
            "keystone": {
                "users": [
                    {
                        "id": "test_user_id",
                        "enabled": True,
                        "tenantId": "test_tenant_id",
                    }
                ],
                "version": "v2.0"
            },
        }

        keystone_v3_component = {
            "keystone": {
                "users": [
                    {
                        "id": "test_user_id",
                        "enabled": True,
                        "default_project_id": "test_tenant_id",
                    }
                ],
                "version": "v3"
            },
        }

        client_provider_mock = self._prepare_client_provider_mock()
        self._update_mock_with_complex_dict(client_provider_mock,
                                            keystone_v2_component)
        kc_v2_info = helpers.get_info_from_os_resource_manager(
            client_provider_mock, consts.OSWL_RESOURCE_TYPES.keystone_user
        )

        client_provider_mock = self._prepare_client_provider_mock()
        self._update_mock_with_complex_dict(client_provider_mock,
                                            keystone_v3_component)
        kc_v3_info = helpers.get_info_from_os_resource_manager(
            client_provider_mock, consts.OSWL_RESOURCE_TYPES.keystone_user
        )

        self.assertEqual(kc_v2_info, kc_v3_info)

    def test_get_info_when_highlevel_attr_is_missing(self):
        keystone_v2_component = {
            "keystone": {
                "users": [
                    {
                        "id": "test_user_id",
                        "enabled": True,
                    }
                ],
                "version": "v2.0"
            },
        }

        expected = [
            {
                "id": "test_user_id",
                "enabled_flag": True,
            },
        ]

        client_provider_mock = self._prepare_client_provider_mock()
        self._update_mock_with_complex_dict(client_provider_mock,
                                            keystone_v2_component)
        try:
            kc_v2_info = helpers.get_info_from_os_resource_manager(
                client_provider_mock, consts.OSWL_RESOURCE_TYPES.keystone_user
            )
        except KeyError:
            raise AssertionError("KeyError must not be raised")

        self.assertItemsEqual(expected, kc_v2_info)

    def test_additional_display_opts_supplied(self):
        expected_display_options = {"search_opts": {"all_tenants": 1}}

        client_provider_mock = self._prepare_client_provider_mock()
        self._update_mock_with_complex_dict(client_provider_mock,
                                            self.components_to_mock)

        helpers.get_info_from_os_resource_manager(
            client_provider_mock, consts.OSWL_RESOURCE_TYPES.vm
        )
        client_provider_mock.nova.servers.list.assert_called_once_with(
            **expected_display_options
        )

        helpers.get_info_from_os_resource_manager(
            client_provider_mock, consts.OSWL_RESOURCE_TYPES.volume
        )
        client_provider_mock.cinder.volumes.list.assert_called_once_with(
            **expected_display_options
        )
