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

from nailgun.api.handlers.base import BaseHandler
from nailgun.api.handlers.base import content_json
from nailgun.api.serializers import task
from nailgun.api.validators import verifications
from nailgun.db.sqlalchemy import models
from nailgun.task.verify_registry import registry


class VerificationHandler(BaseHandler):

    serializer = task.TaskSerializer
    validator = verifications.VerificationsValidator

    @content_json
    def PUT(self, cluster_id):
        self.get_object_or_404(models.Cluster, cluster_id)
        data = self.checked_data()
        task_manager_cls = registry.get_task_manager(data['task_name'])
        task_manager = task_manager_cls(cluster_id=cluster_id)
        args = data.get('args', ())
        kwargs = data.get('kwargs', {})
        return task_manager.execute(*args, **kwargs)
