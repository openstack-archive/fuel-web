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

from nailgun.utils import ObjectMapper

_object_mapper = ObjectMapper({
    'NailgunObject': 'nailgun.objects.base',
    'NailgunCollection': 'nailgun.objects.base',

    'ActionLog': 'nailgun.objects.action_log',
    'ActionLogCollection': 'nailgun.objects.action_log',

    'OpenStackWorkloadStats': 'nailgun.objects.oswl',
    'OpenStackWorkloadStatsCollection': 'nailgun.objects.oswl',

    'Release': 'nailgun.objects.release',
    'ReleaseCollection': 'nailgun.objects.release',

    'Attributes': 'nailgun.objects.cluster',
    'Cluster': 'nailgun.objects.cluster',
    'ClusterCollection': 'nailgun.objects.cluster',
    'VmwareAttributes': 'nailgun.objects.cluster',

    'Task': 'nailgun.objects.task',
    'TaskCollection': 'nailgun.objects.task',

    'Notification': 'nailgun.objects.notification',
    'NotificationCollection': 'nailgun.objects.notification',

    'Node': 'nailgun.objects.node',
    'NodeCollection': 'nailgun.objects.node',

    'CapacityLog': 'nailgun.objects.capacity',

    'MasterNodeSettings': 'nailgun.objects.master_node_settings',

    'NodeGroup': 'nailgun.objects.node_group',
    'NodeGroupCollection': 'nailgun.objects.node_group',

    'Plugin': 'nailgun.objects.plugin',
    'PluginCollection': 'nailgun.objects.plugin',

    'NetworkGroup': 'nailgun.objects.network_group',
    'NetworkGroupCollection': 'nailgun.objects.network_group'})
