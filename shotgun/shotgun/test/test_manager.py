#    Copyright 2015 Mirantis, Inc.
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

import tempfile

import mock

from shotgun.manager import Manager
from shotgun.test import base


class TestManager(base.BaseTestCase):

    @mock.patch('shotgun.manager.Driver.getDriver')
    @mock.patch('shotgun.manager.utils.execute')
    @mock.patch('shotgun.manager.utils.compress')
    def test_snapshot(self, mcompress, mexecute, mget):
        data = {
            "type": "file",
            "path": "/remote_dir/remote_file",
            "host": {
                "address": "remote_host",
            },
        }
        conf = mock.MagicMock()
        conf.target = "/target/data"
        conf.objects = [data]
        conf.lastdump = tempfile.mkstemp()[1]
        manager = Manager(conf)
        manager.snapshot()
        mget.assert_called_once_with(data, conf)
        mexecute.assert_called_once_with('rm -rf /target')
