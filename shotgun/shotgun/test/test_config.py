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

import re
import time

import mock

from shotgun.config import Config


def test_timestamp():
    t = time.localtime()
    with mock.patch('shotgun.config.time.localtime', return_value=t):
        conf = Config({})
        stamped = conf._timestamp("sample")

    assert stamped == "sample-{0}".format(
        time.strftime('%Y-%m-%d_%H-%M-%S', t))


def test_target_timestamp():
    conf = Config({
        "target": "/tmp/sample",
        "timestamp": True
    })

    assert re.search(
        ur"\/tmp\/sample\-[\d]{4}\-[\d]{2}\-[\d]{2}_"
        "([\d]{2}\-){2}[\d]{2}",
        conf.target
    )


@mock.patch('shotgun.config.settings')
def test_timeout(m_settings):
    conf = Config({})
    assert conf.timeout is m_settings.DEFAULT_TIMEOUT


def test_pass_default_timeout():
    timeout = 1345
    conf = Config({
        'timeout': timeout,
    })
    assert conf.timeout == timeout
