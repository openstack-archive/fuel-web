# -*- coding: utf-8 -*-

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


from unittest2.case import TestCase

from nailgun.orchestrator.group_patterns import GroupPatterns


class TestGroupPatterns(TestCase):
    def test_no_match(self):
        pattern = GroupPatterns(name='name')
        groups = ('name1', 'name2')

        self.assertFalse(pattern.match(groups))

    def test_match_by_all(self):
        pattern = GroupPatterns(name='name')
        groups = ('*', 'name1')

        self.assertTrue(pattern.match(groups))

    def test_match_by_scope(self):
        pattern = GroupPatterns(name='name-scope')
        groups = ('/scope/', 'name2')

        self.assertTrue(pattern.match(groups))

    def test_no_match_by_except(self):
        pattern = GroupPatterns(name='name')
        groups = ('*', '!name')

        self.assertFalse(pattern.match(groups))

    def test_no_match_by_except_scope(self):
        pattern = GroupPatterns(name='name-scope')
        groups = ('*', '!/scope/')

        self.assertFalse(pattern.match(groups))

    def test_no_match_by_except_with_name(self):
        pattern = GroupPatterns(name='name')
        groups = ('name', '!name')

        self.assertFalse(pattern.match(groups))

    def test_no_match_by_except_scope_with_name(self):
        pattern = GroupPatterns(name='name-scope')
        groups = ('name-scope', '!/scope/')

        self.assertFalse(pattern.match(groups))

    def test_no_match_without_pattern(self):
        pattern = GroupPatterns(name='name')
        groups = ('name', 'name2')

        self.assertFalse(pattern.match(groups))

    def test_all_matches(self):
        pattern = GroupPatterns()
        groups_names = ['name1']
        groups = ('name1', 'name2')

        self.assertEqual(
            pattern.all_matches(groups_names, groups), groups_names)

    def test_all_matches_for_all(self):
        pattern = GroupPatterns()
        groups_names = ['*']
        groups = ['name1', 'name2']

        self.assertEqual(
            pattern.all_matches(groups_names, groups), groups)

    def test_all_matches_for_scope(self):
        pattern = GroupPatterns()
        groups_names = ('/scope/',)
        groups = ('name1', 'name2', 'name-scope', 'scope', 'scope2')

        self.assertEqual(pattern.all_matches(groups_names, groups),
                         ['name-scope', 'scope'])

    def test_all_matches_for_all_except_one(self):
        pattern = GroupPatterns()
        groups_names = ('*', '!name2')
        groups = ('name1', 'name2')

        self.assertEqual(pattern.all_matches(groups_names, groups),
                         ['name1'])

    def test_all_matches_for_all_except_scope(self):
        pattern = GroupPatterns()
        groups_names = ('*', '!/scope/')
        groups = ('name1', 'name2', 'scope', 'name-scope', 'scope2')

        self.assertEqual(pattern.all_matches(groups_names, groups),
                         ['name1', 'name2', 'scope2'])
