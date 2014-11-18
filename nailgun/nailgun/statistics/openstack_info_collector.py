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

import os

from novaclient import client as nova_client

from nailgun.network import manager


class OpenStackInfoCollector(object):

    def __init__(self, cluster, cluster_nodes):
        proxy_port = 8888
        proxy_host = self.get_online_controller_ip(cluster_nodes)
        os.environ["http_proxy"] = "http://{0}:{1}".format(proxy_host,
                                                           proxy_port)

        access_data = cluster.attributes.editable["access"]
        self.openstack_user = access_data["user"]["value"]
        self.openstack_password = access_data["password"]["value"]
        self.openstack_tenant = access_data["tenant"]["value"]
        self.service_type = "compute"

        public_vip = self.get_public_vip(cluster)
        self.auth_url = "http://{0}:5000/v2.0/".format(public_vip)

    def get_online_controller_ip(nodes):
        online_controllers = filter(
            lambda node: "controller" in node.roles and node.online is True,
            nodes
        )
        proxy_host = online_controllers[0].ip
        return proxy_host

    def get_public_vip(self, cluster):
        return manager.NetworkManager.assign_vip(cluster.id, "public")

    def get_instances_count(self):
        c = nova_client.Client(
            "2",
            self.openstack_user,
            self.openstack_password,
            self.openstack_tenant,
            self.auth_url,
            service_type=self.service_type
        )
        return len(c.servers.list())

    def get_info(self):
        openstack_info = {
            "instances_count": self.get_instances_count()
        }

        return openstack_info
