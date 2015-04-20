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
from mock import patch
from mock import PropertyMock

from nailgun.test.base import BaseTestCase

from nailgun import consts
from nailgun.objects import Cluster
from nailgun.settings import settings
from nailgun.statistics import errors
from nailgun.statistics.oswl import helpers


class TestOpenStackClientProvider(BaseTestCase):

    @patch("nailgun.statistics.oswl.helpers.ClientProvider.credentials",
           new_callable=PropertyMock)
    def test_clients_providing(self, creds_mock):
        fake_credentials = (
            "fake_username",
            "fake_password",
            "fake_tenant_name",
            "fake_auth_url"
        )
        auth_kwargs = {
            "username": fake_credentials[0],
            "password": fake_credentials[1],
            "tenant_name": fake_credentials[2],
            "project_name": fake_credentials[2],
            "auth_url": fake_credentials[3]
        }

        creds_mock.return_value = fake_credentials
        client_provider = helpers.ClientProvider(cluster=None)

        nova_client_path = ("nailgun.statistics.oswl."
                            "helpers.nova_client.Client")
        cinder_client_path = ("nailgun.statistics.oswl."
                              "helpers.cinder_client.Client")

        return_value_mock = Mock()

        with patch(nova_client_path,
                   Mock(return_value=return_value_mock)) as nova_client_mock:

            self.assertTrue(client_provider.nova is return_value_mock)

            client_provider.nova

            nova_client_mock.assert_called_once_with(
                settings.OPENSTACK_API_VERSION["nova"],
                *fake_credentials,
                service_type=consts.NOVA_SERVICE_TYPE.compute
            )

        with patch(cinder_client_path,
                   Mock(return_value=return_value_mock)) as cinder_client_mock:

            self.assertTrue(client_provider.cinder is return_value_mock)

            client_provider.cinder

            cinder_client_mock.assert_called_once_with(
                settings.OPENSTACK_API_VERSION["cinder"],
                *fake_credentials
            )

        with patch.object(client_provider, "_get_keystone_client",
                          return_value=return_value_mock) as get_kc_mock:
            kc = client_provider.keystone
            self.assertTrue(kc is return_value_mock)

            client_provider.keystone

            get_kc_mock.assert_called_with_once(**auth_kwargs)

    def test_fail_if_no_online_controllers(self):
        self.env.create(
            nodes_kwargs=[{"online": False, "roles": ["controller"]}]
        )
        cluster = self.env.clusters[0]
        client_provider = helpers.ClientProvider(cluster)

        with self.assertRaises(errors.NoOnlineControllers):
            client_provider.credentials

    @patch("nailgun.statistics.oswl.helpers.keystone_client_v3.Client")
    @patch("nailgun.statistics.oswl.helpers.keystone_client_v2.Client")
    @patch("nailgun.statistics.oswl.helpers.keystone_discover.Discover")
    def test_get_keystone_client(self, kd_mock, kc_v2_mock, kc_v3_mock):
        version_data_v2 = [{"version": (2, 0)}]
        version_data_v3 = [{"version": (3, 0)}]
        mixed_version_data = [{"version": (4, 0)}, {"version": (3, 0)}]
        not_supported_version_data = [{"version": (4, 0)}]

        auth_creds = {"auth_url": "fake"}

        client_provider = helpers.ClientProvider(cluster=None)

        discover_inst_mock = Mock()
        kd_mock.return_value = discover_inst_mock

        kc_v2_inst_mock = Mock()
        kc_v2_mock.return_value = kc_v2_inst_mock

        kc_v3_inst_mock = Mock()
        kc_v3_mock.return_value = kc_v3_inst_mock

        def check_returned(version_data, client_class_mock, client_inst_mock):
            discover_inst_mock.version_data = Mock(return_value=version_data)

            kc_client_inst = client_provider._get_keystone_client(auth_creds)

            kd_mock.assert_called_with(**auth_creds)

            self.assertTrue(kc_client_inst is client_inst_mock)

            client_class_mock.assert_called_with(**auth_creds)

        check_returned(version_data_v2, kc_v2_mock, kc_v2_inst_mock)
        check_returned(version_data_v3, kc_v3_mock, kc_v3_inst_mock)
        check_returned(mixed_version_data, kc_v3_mock, kc_v3_inst_mock)

        fail_message = ("Failed to discover keystone version "
                        "for auth_url {0}"
                        .format(auth_creds["auth_url"]))

        discover_inst_mock.version_data = \
            Mock(return_value=not_supported_version_data)

        self.assertRaisesRegexp(
            Exception,
            fail_message,
            client_provider._get_keystone_client,
            auth_creds
        )

    def test_get_auth_credentials(self):
        expected_username = "test"
        expected_password = "test"
        expected_tenant = "test"
        expected_auth_host = "0.0.0.0"
        expected_auth_url = "http://{0}:{1}/{2}/".format(
            expected_auth_host, settings.AUTH_PORT,
            settings.OPENSTACK_API_VERSION["keystone"])

        expected = (expected_username, expected_password, expected_tenant,
                    expected_auth_url)

        cluster = self.env.create_cluster(api=False)

        default_access_data = Cluster.get_creds(cluster)
        default_username = default_access_data["user"]["value"]
        default_password = default_access_data["password"]["value"]
        default_tenant = default_access_data["tenant"]["value"]

        expected_default = (default_username, default_password,
                            default_tenant, expected_auth_url)

        get_host_for_auth_path = ("nailgun.statistics.utils."
                                  "get_mgmt_ip_of_cluster_controller")

        def check_creds(updated_attrs, expected_creds):
            Cluster.update_attributes(cluster, updated_attributes)
            with patch(get_host_for_auth_path,
                       return_value=expected_auth_host):
                client_provider = helpers.ClientProvider(cluster)
                creds = client_provider.credentials

                self.assertEqual(expected_creds, creds)

        updated_attributes = {
            "editable": {
                "access": {
                    "user": {"value": default_username},
                    "password": {"value": default_password},
                    "tenant": {"value": default_tenant}
                }
            }
        }

        check_creds(updated_attributes, expected_default)

        updated_attributes = {
            "editable": {
                "workloads_collector": {
                    "user": {"value": expected_username},
                    "password": {"value": expected_password},
                    "tenant": {"value": expected_tenant}
                }
            }
        }

        check_creds(updated_attributes, expected)
