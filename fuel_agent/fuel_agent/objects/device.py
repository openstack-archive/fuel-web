# Copyright 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from fuel_agent import errors


class Loop(object):
    def __init__(self, name=None):
        self.name = name

    def __str__(self):
        if self.name:
            return self.name
        raise errors.WrongDeviceError(
            'Loop device has not been initialized properly: '
            'name={0}'.format(self.name))
