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

from nailgun import objects


def notify(topic, message, cluster_id=None, node_id=None, task_uuid=None):
    objects.Notification.create({
        "topic": topic,
        "message": message,
        "cluster_id": cluster_id,
        "node_id": node_id,
        "task_uuid": task_uuid
    })
