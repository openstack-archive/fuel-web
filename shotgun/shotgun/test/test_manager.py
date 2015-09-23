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

import mock

from shotgun.manager import Manager


@mock.patch('shotgun.manager.Driver.getDriver')
@mock.patch('shotgun.manager.utils.execute')
@mock.patch('shotgun.manager.utils.compress')
def test_snapshot(mcompress, mexecute, mget, fake_conf, tmpdir):
    data = {
        "type": "file",
        "path": "/remote_dir/remote_file",
        "host": {
            "address": "remote_host",
        },
    }
    fake_conf.target = "/target/data"
    fake_conf.objects = [data]
    fake_conf.lastdump = tmpdir.join("last_snapshot").strpath
    manager = Manager(fake_conf)
    manager.snapshot()
    mget.assert_called_once_with(data, fake_conf)
    mexecute.assert_called_once_with('rm -rf /target')
