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

import pygit2

from fuel_agent_ci import utils


def repo_clone(repo):
    return pygit2.clone_repository(
        repo.url, os.path.join(repo.env.envdir, repo.path),
        checkout_branch=repo.branch)


def repo_clean(repo):
    utils.execute('rm -rf %s' % os.path.join(repo.env.envdir, repo.path))


def repo_status(repo):
    try:
        pygit2.discover_repository(os.path.join(repo.env.envdir, repo.path))
    except KeyError:
        return False
    return True
