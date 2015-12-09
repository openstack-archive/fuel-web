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


from nailgun.objects.base import NailgunObject
from nailgun.objects.base import NailgunCollection
from nailgun.objects.base import ProxiedNailgunObject

from nailgun.objects.action_log import ActionLog
from nailgun.objects.action_log import ActionLogCollection

from nailgun.objects.oswl import OpenStackWorkloadStats
from nailgun.objects.oswl import OpenStackWorkloadStatsCollection

from nailgun.objects.release import Release
from nailgun.objects.release import ReleaseCollection

from nailgun.objects.cluster import Attributes
from nailgun.objects.cluster import Cluster
from nailgun.objects.cluster import ClusterCollection
from nailgun.objects.cluster import VmwareAttributes

from nailgun.objects.task import Task
from nailgun.objects.task import TaskCollection

from nailgun.objects.notification import Notification
from nailgun.objects.notification import NotificationCollection

from nailgun.objects.network_group import NetworkGroup
from nailgun.objects.network_group import NetworkGroupCollection

from nailgun.objects.ip_address import IPAddr
from nailgun.objects.ip_address import IPAddrCollection
from nailgun.objects.ip_address import IPAddrRange

from nailgun.objects.node import Node
from nailgun.objects.node import NodeCollection

from nailgun.objects.capacity import CapacityLog

from nailgun.objects.master_node_settings import MasterNodeSettings

from nailgun.objects.node_group import NodeGroup
from nailgun.objects.node_group import NodeGroupCollection

from nailgun.objects.plugin import Plugin
from nailgun.objects.plugin import PluginCollection
from nailgun.objects.plugin import ClusterPlugins

from nailgun.objects.plugin_link import PluginLink
from nailgun.objects.plugin_link import PluginLinkCollection

from nailgun.objects.cluster_plugin_link import ClusterPluginLink
from nailgun.objects.cluster_plugin_link import ClusterPluginLinkCollection
from nailgun.objects.openstack_config import OpenstackConfig
from nailgun.objects.openstack_config import OpenstackConfigCollection

from nailgun.objects.interface import NIC
from nailgun.objects.interface import NICCollection

from nailgun.objects.bond import Bond
from nailgun.objects.bond import BondCollection
