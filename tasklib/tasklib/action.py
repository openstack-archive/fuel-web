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


class Action(object):

    def __init__(self, task, action):
        self.task = task
        self.action = action

    def run(self):
        raise NotImplementedError('Should be implemented by action driver.')

    def report_write(self):
        return self.task.report_write(self.action)

    def report_read(self):
        return self.task.report_read(self.action)

    def report_output(self):
        return self.task.report_output(self.action)

    def report_remove(self):
        return self.task.report_remove(self.action)

    def report_file_path(self):
        return self.task.report_file_path(self.action)
