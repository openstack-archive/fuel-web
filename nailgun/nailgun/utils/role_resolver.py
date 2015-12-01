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

import abc
from collections import defaultdict
import random
import re

import six

from nailgun import consts
from nailgun.logger import logger
from nailgun import objects


def compile_strict_pattern(pattern):
    """Makes strong search pattern.

    :param pattern: the pattern to match
    :return: the compiled regular expression
    """
    return re.compile(r"^{0}$".format(pattern))


@six.add_metaclass(abc.ABCMeta)
class RoleResolver(object):
    @abc.abstractmethod
    def resolve(self, roles, policy=None):
        """Resolve roles to IDs of nodes.

        :param roles: the required roles
        :type roles: list|str
        :param policy: the nodes select policy any|all
        :type policy: str
        :return: the list of nodes
        """


class NullResolver(RoleResolver):
    def __init__(self, nodes):
        self.nodes = nodes

    def resolve(self, roles, policy=None):
        return self.nodes


class PatternBasedRoleResolver(RoleResolver):
    """Helper class to find nodes by role."""

    SPECIAL_ROLES = {
        None: [None],
        consts.MASTER_ROLE: [consts.MASTER_ROLE]
    }

    def __init__(self, nodes):
        self.mapping = defaultdict(set)
        for node in nodes:
            for r in objects.Node.all_roles(node):
                self.mapping[r].add(node.uid)

    def resolve(self, roles, policy=None):
        if isinstance(roles, six.string_types) and roles in self.SPECIAL_ROLES:
            result = self.SPECIAL_ROLES[roles]
        elif roles == consts.ALL_ROLES:
            result = list(set(
                uid for nodes in six.itervalues(self.mapping) for uid in nodes
            ))
        elif isinstance(roles, (list, tuple)):
            result = set()
            for role in roles:
                pattern = compile_strict_pattern(role)
                for node_role, nodes_ids in six.iteritems(self.mapping):
                    if pattern.match(node_role):
                        result.update(nodes_ids)
            result = list(result)
        else:
            logger.warn(
                'Wrong roles format, `roles` should be a list or "*": %s',
                roles
            )
            return []

        if result and policy == consts.NODE_RESOLVE_POLICY.any:
            result = [random.choice(result)]

        logger.debug(
            "Role '%s' and policy '%s' was resolved to: ",
            ', '.join(result)
        )
        return result
