# Copyright 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from fuel_agent_ci.drivers import common_driver
from fuel_agent_ci.drivers import fabric_driver
from fuel_agent_ci.drivers import libvirt_driver
from fuel_agent_ci.drivers import pygit2_driver
from fuel_agent_ci.drivers import simple_http_driver


class Driver(object):
    default_hierarchy = {
        # these methods are from common_driver
        'artifact_get': common_driver,
        'artifact_clean': common_driver,
        'artifact_status': common_driver,

        # these methods are from fabric_driver
        'ssh_status': fabric_driver,
        'ssh_put_content': fabric_driver,
        'ssh_put_file': fabric_driver,
        'ssh_run': fabric_driver,

        # these methods are from libvirt_driver
        'net_start': libvirt_driver,
        'net_stop': libvirt_driver,
        'net_status': libvirt_driver,
        'vm_start': libvirt_driver,
        'vm_stop': libvirt_driver,
        'vm_status': libvirt_driver,
        'dhcp_start': libvirt_driver,
        'dhcp_stop': libvirt_driver,
        'dhcp_status': libvirt_driver,
        'tftp_start': libvirt_driver,
        'tftp_stop': libvirt_driver,
        'tftp_status': libvirt_driver,

        # these methods are from pygit2_driver
        'repo_clone': pygit2_driver,
        'repo_clean': pygit2_driver,
        'repo_status': pygit2_driver,

        # these methods are from simple_http_driver
        'http_start': simple_http_driver,
        'http_stop': simple_http_driver,
        'http_status': simple_http_driver,
    }

    def __init__(self, hierarchy=None):
        self.hierarchy = self.default_hierarchy
        self.hierarchy.update(hierarchy or {})

    def __getattr__(self, item):
        return getattr(self.hierarchy[item], item)
