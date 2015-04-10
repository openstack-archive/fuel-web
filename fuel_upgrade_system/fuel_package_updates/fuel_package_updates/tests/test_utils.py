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

import unittest2

from fuel_package_updates import utils


class TestUtils(unittest2.TestCase):

    def test_repo_merge(self):
        repo_mos_updates = {
            "type": "deb",
            "name": "MOS-Updates",
            "uri": "some/uri",
        }
        repo_mos_security = {
            "type": "deb",
            "name": "mos6.1-security",
            "uri": "some/uri",
        }
        other_repos_moc_security = {
            "type": "rpm",
            "name": "mos6.1-security",
            "uri": "some/other_uri",
        }
        list_a = [repo_mos_updates, repo_mos_security]
        list_b = [other_repos_moc_security]
        check_merged = [repo_mos_updates, other_repos_moc_security]

        merged_repos = utils.repo_merge(list_a, list_b)

        self.assertListEqual(merged_repos, check_merged)
