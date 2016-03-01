# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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

from nailgun.objects.serializers.base import BasicSerializer
import time


class DeploymentHistorySerializer(BasicSerializer):

    fields = (
        "deployment_graph_task_name",
        "node_id",
        "time_start",
        "time_end",
        "status",
        "custom"
    )

    @classmethod
    def serialize(cls, instance, fields=None):
        data_dict = super(DeploymentHistorySerializer, cls).serialize(
            instance,
            fields)
        if instance.time_start:
            data_dict['time_start'] = int(time.mktime(
                instance.time_start.timetuple()))
        if instance.time_end:
            data_dict['time_end'] = int(time.mktime(
                instance.time_end.timetuple()))
        return data_dict
