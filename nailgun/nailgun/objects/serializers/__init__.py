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

from nailgun.objects.serializers.action_log import ActionLogSerializer

from nailgun.objects.serializers.base import BasicSerializer

from nailgun.objects.serializers.cluster import ClusterSerializer
from nailgun.objects.serializers.cluster import AttributesSerializer

from nailgun.objects.serializers.master_node_settings import \
    MasterNodeSettingsSerializer

from nailgun.objects.serializers.network_configuration import \
    NetworkConfigurationSerializer

from nailgun.objects.serializers.network_group import NetworkGroupSerializer

from nailgun.objects.serializers.node import NodeSerializer
from nailgun.objects.serializers.node import NodeInterfacesSerializer

from nailgun.objects.serializers.node_group import NodeGroupSerializer

from nailgun.objects.serializers.notification import NotificationSerializer

from nailgun.objects.serializers.oswl import OpenStackWorkloadStatsSerializer

from nailgun.objects.serializers.plugin import PluginSerializer

from nailgun.objects.serializers.release import ReleaseSerializer

from nailgun.objects.serializers.role import RoleSerializer

from nailgun.objects.serializers.task import TaskSerializer
