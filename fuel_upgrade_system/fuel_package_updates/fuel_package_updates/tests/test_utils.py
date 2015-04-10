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
        other_repos_mos_security = {
            "type": "deb",
            "name": "mos6.1-security",
            "uri": "some/other_uri",
        }
        list_a = [repo_mos_updates, repo_mos_security]
        list_b = [other_repos_mos_security]
        check_merged = [repo_mos_updates, other_repos_mos_security]

        merged_repos = utils.repo_merge(list_a, list_b)

        self.assertListEqual(merged_repos, check_merged)

    def test_repo_merge_ordering(self):
        ubuntu_repo = {
            "type": "deb",
            "name": "ubuntu",
            "uri": "some/uri main",
        }
        other_repo_name = 'someother'
        list_a = [
            {
                "type": "deb",
                "name": other_repo_name,
                "uri": "some/uri main other",
            },
            ubuntu_repo,
        ]

        list_b = [
            {
                "type": "deb",
                "name": "other",
                "uri": "some/uri main",
            },
            {
                "type": "deb",
                "name": other_repo_name,
                "uri": "some/uri main other",
            },
        ]

        merged_repos = utils.repo_merge(list_a, list_b)

        self.assertEqual(len(merged_repos), 3)
        self.assertEqual(merged_repos[0], ubuntu_repo)

    def test_repo_merge_deletes(self):
        list_a = [
            {
                "type": "deb",
                "name": "ubuntu",
                "uri": "some/uri main",
            },
            {
                "type": "deb",
                "name": "ubuntu-security",
                "uri": "some/uri main",
            },
            {
                "type": "deb",
                "name": "someother",
                "uri": "some/uri main",
            }
        ]

        list_b = [
            {"name": "ubuntu", "delete": True},
            {"name": "ubuntu-security", "delete": True},
        ]

        merged_repos = utils.repo_merge(list_a, list_b)
        self.assertEqual(len(merged_repos), 1)

        for repo in list_b:
            self.assertNotIn(repo, merged_repos)
