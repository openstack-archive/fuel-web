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
    """

    def __init__(self, name=consts.GROUP_NAME_PATTERN):
        self.all = '^\*$'
        self.exclude = '^!{0}$'.format(name)

        scope_name = name.split(consts.GROUP_NAME_DELIMITER)[-1]\
            if name != consts.GROUP_NAME_PATTERN else name

        self.scope = '^/{0}/$'.format(scope_name)
        self.exclude_scope = '^!/{0}/$'.format(scope_name)

    def match(self, groups):
        """Check if list of groups matches pattern:
        1. Check if list of groups contains except
           or except scope pattern
        2. Check if list of groups contains all pattern
           or scope pattern

        :param groups: list of groups names
        :returns: boolean value
        """

        pattern_in_groups = lambda p:\
            next((g for g in groups if re.match(p, g)), None)

        if (pattern_in_groups(self.exclude) or
                pattern_in_groups(self.exclude_scope)):
            return False
        elif pattern_in_groups(self.all) or pattern_in_groups(self.scope):
            return True

        return False

    def all_matches(self, groups_names, groups):
        """Get all matches for group_names in
        list of groups by pattern

        :param groups_names: name of groups to check
        :param groups: list of groups names
        :returns: list of group names
        """

        grps = []
        groups_to_del = []
        scopes_to_del = []

        for group_name in groups_names:
            if re.match(self.all, group_name):
                grps += [g for g in groups]
            elif re.match(self.scope, group_name):
                grps += [g for g in groups if
                         re.search('(^|-){0}$'.format(group_name[1:-1]), g)]
            elif re.match(self.exclude, group_name):
                groups_to_del.append(group_name[1:])
            elif re.match(self.exclude_scope, group_name):
                scopes_to_del.append(group_name[2:-1])
            else:
                grps.append(group_name)

        matches = filter(lambda gr: (gr not in groups_to_del and
                                     gr.split(consts.GROUP_NAME_DELIMITER)[-1]
                                     not in scopes_to_del), grps)

        return matches
