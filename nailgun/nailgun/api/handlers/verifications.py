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

from nailgun.api.handlers import base
from nailgun.api.validators import verifications
from nailgun.task import manager


class VerificationHandler(base.DeferredTaskHandler):

    validator = verifications.VerificationsValidator

    @property
    def task_manager(self):
        data = self.checked_data()
        return manager.verify_actions[data['task_name']]
