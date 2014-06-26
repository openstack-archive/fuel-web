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

from oslo.config import cfg

opts = [
    cfg.StrOpt(
        'partition_data_file',
        default='/tmp/partition.json',
        help='Parititoning data file'
    ),
]

CONF = cfg.CONF
CONF.register_opts(opts)


class ReadFile(object):
    def __init__(self, filename):
        self.filename = filename

    def get(self):
        with open(self.filename) as f:
            return f.read()
