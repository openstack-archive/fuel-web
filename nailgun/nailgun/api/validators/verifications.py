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

from nailgun.api.validators import base
from nailgun.errors import errors
from nailgun.task.verify_registry import registry


class VerificationsValidator(base.BasicValidator):

    @classmethod
    def validate(cls, data):
        data = super(VerificationsValidator, cls).validate(data)
        if 'task_name' not in data:
            raise errors.InvalidData('Field task_name is required.')
        if not registry.has_task_manager(data['task_name']):
            raise errors.InvalidData(
                'Please provide valid task_name.'
                ' Availbale: {0}'.format(registry.available_managers()))
        return data
