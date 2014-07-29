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

import os
import requests

from fuel_agent_ci import utils


def artifact_get(artifact):
    with open(os.path.join(artifact.env.envdir, artifact.path), 'wb') as f:
        for chunk in requests.get(
                artifact.url, stream=True).iter_content(1048576):
            f.write(chunk)
        f.flush()
    utils.execute(artifact.unpack, cwd=artifact.env.envdir)


def artifact_clean(artifact):
    utils.execute(artifact.clean, cwd=artifact.env.envdir)


def artifact_status(artifact):
    return os.path.isfile(os.path.join(artifact.env.envdir, artifact.path))


def dhcp_start(*args, **kwargs):
    raise NotImplementedError


def dhcp_stop(*args, **kwargs):
    raise NotImplementedError


def dhcp_status(*args, **kwargs):
    raise NotImplementedError


def http_start(*args, **kwargs):
    raise NotImplementedError


def http_stop(*args, **kwargs):
    raise NotImplementedError


def http_status(*args, **kwargs):
    raise NotImplementedError


def net_start(*args, **kwargs):
    raise NotImplementedError


def net_stop(*args, **kwargs):
    raise NotImplementedError


def net_status(*args, **kwargs):
    raise NotImplementedError


def repo_clone(*args, **kwargs):
    raise NotImplementedError


def repo_clean(*args, **kwargs):
    raise NotImplementedError


def repo_status(*args, **kwargs):
    raise NotImplementedError


def ssh_status(*args, **kwargs):
    raise NotImplementedError


def ssh_put_content(*args, **kwargs):
    raise NotImplementedError


def ssh_put_file(*args, **kwargs):
    raise NotImplementedError


def ssh_run(*args, **kwargs):
    raise NotImplementedError


def tftp_start(*args, **kwargs):
    raise NotImplementedError


def tftp_stop(*args, **kwargs):
    raise NotImplementedError


def tftp_status(*args, **kwargs):
    raise NotImplementedError


def vm_start(*args, **kwargs):
    raise NotImplementedError


def vm_stop(*args, **kwargs):
    raise NotImplementedError


def vm_status(*args, **kwargs):
    raise NotImplementedError
