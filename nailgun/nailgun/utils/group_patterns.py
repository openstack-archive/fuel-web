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

"""Group patterns for deployment tasks"""

import re

from nailgun import consts


class GroupPatterns(object):
    """Patterns for deployment tasks groups:

    *               - all groups
    !<group_name>   - exclude group
    /<scope_name>/  - all groups from scope
    !/<scope_name>/ - exclude scope of groups

    groups may be included in some scope
    in this case group_name should have
    a suffix (scope_name) after predefined delimiter

    Example:
    currently delimiter is "-"
    for groups: primary-mongo, mongo, compute

    *             -> primary-mongo, mongo, compute
    *, !compute   -> primary-mongo, mongo
    /mongo/       -> primary-mongo, mongo
    *, !/mongo/   -> compute
    """

    def __init__(self, name=consts.GROUP_NAME_PATTERN):
        self.all = re.compile('^\*$')
        self.exclude = re.compile('^!({0})$'.format(name))

        scope_name = name.split(consts.GROUP_NAME_DELIMITER)[-1]\
            if name != consts.GROUP_NAME_PATTERN else name

        self.scope = re.compile('^/({0})/$'.format(scope_name))
        self.exclude_scope = re.compile('^!/({0})/$'.format(scope_name))

    @staticmethod
    def pattern_in_groups(p, groups):
        return next((g for g in groups if p.search(g)), None)

    def match(self, groups):
        """Check if list of groups matches pattern:
        1. Check if list of groups contains except
           or except scope pattern
        2. Check if list of groups contains all pattern
           or scope pattern

        :param groups: list of groups names
        :returns: boolean value
        """

        if (GroupPatterns.pattern_in_groups(self.exclude, groups) or
                GroupPatterns.pattern_in_groups(self.exclude_scope, groups)):
            return False
        elif (GroupPatterns.pattern_in_groups(self.all, groups) or
                GroupPatterns.pattern_in_groups(self.scope, groups)):
            return True

        return False

    def _build_pattern(self, groups_name_patterns):
        positive = []
        negative = []
        general_pattern = re.compile('^!*/*({0})/*$'.
                                     format(consts.GROUP_NAME_PATTERN))

        for grp_pattern in groups_name_patterns:
            group_name = re.sub(general_pattern, r'\1', grp_pattern)

            if self.all.search(grp_pattern):
                positive.append(consts.GROUP_NAME_PATTERN)
            elif self.scope.search(grp_pattern):
                positive.append(group_name)
                positive.append('{0}-{1}'.format(consts.GROUP_NAME_PATTERN,
                                                 group_name))
            elif self.exclude.search(grp_pattern):
                negative.append(group_name)
            elif self.exclude_scope.search(grp_pattern):
                negative.append(group_name)
                negative.append('{0}-{1}'.format(consts.GROUP_NAME_PATTERN,
                                                 group_name))
            else:
                positive.append(group_name)

        return re.compile('(?!^({0})$)^({1})$'.
                          format('|'.join(negative), '|'.join(positive)))

    def all_matches(self, groups_name_patterns, groups):
        """Get all matches for group_names in
        list of groups by pattern

        :param groups_name_patterns: name of groups to check
        :param groups: list of groups names
        :returns: list of group names
        """

        pattern = self._build_pattern(groups_name_patterns)
        matches = [g for g in groups if pattern.search(g)]

        return matches
