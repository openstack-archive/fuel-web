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
#    under the License

from .base import BasicSerializer

from .action_log import ActionLogSerializer

from .cluster import AttributesSerializer
from .cluster import ClusterSerializer

from .component import ComponentSerializer

from .master_node_settings import MasterNodeSettingsSerializer

from .network_configuration import NetworkConfigurationSerializer
from .network_configuration import NeutronNetworkConfigurationSerializer
from .network_configuration import NovaNetworkConfigurationSerializer

from .network_group import NetworkGroupSerializer

from .node_group import NodeGroupSerializer

from .node import NodeSerializer
from .node import NodeInterfacesSerializer

from .notification import NotificationSerializer

from .oswl import OpenStackWorkloadStatsSerializer

from .plugin import PluginSerializer

from .release import ReleaseSerializer

from .role import RoleSerializer

from .task import TaskSerializer
