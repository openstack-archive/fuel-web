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

import six

from nailgun import consts
from nailgun.logger import logger
from nailgun import objects
from nailgun.policy.name_match import NameMatchingPolicy


@six.add_metaclass(abc.ABCMeta)
class BaseRoleResolver(object):
    """Helper class to find nodes by role."""

    @abc.abstractmethod
    def resolve(self, roles, policy=None):
        """Resolve roles to IDs of nodes.

        :param roles: the required roles
        :type roles: list|str
        :param policy: the policy to filter the list of resolved nodes
                       can be any|all
                       any means need to return any node from resolved
                       all means need to return all resolved nodes
        :type policy: str
        :return: the list of nodes
        """


class NullResolver(BaseRoleResolver):
    """The implementation of RoleResolver

    that returns only specified IDs.
    """
    def __init__(self, nodes_ids):
        self.nodes_ids = nodes_ids

    def resolve(self, roles, policy=None):
        return self.nodes_ids


class RoleResolver(BaseRoleResolver):
    """The general role resolver.

    Allows to use patterns in name of role
    """

    # the mapping roles, those are resolved to known list of IDs
    # master is used to run tasks on master node
    SPECIAL_ROLES = {
        consts.TASK_ROLES.master: [consts.MASTER_NODE_UID]
    }

    def __init__(self, nodes):
        """Initializes.

        :param nodes: the sequence of node objects
        """
        self.__mapping = defaultdict(set)
        for node in nodes:
            for r in objects.Node.all_roles(node):
                self.__mapping[r].add(node.uid)

    def resolve(self, roles, policy=None):
        if roles == consts.TASK_ROLES.all:
            result = set(
                uid for nodes in six.itervalues(self.__mapping)
                for uid in nodes
            )
        elif isinstance(roles, six.string_types) \
                and roles in self.SPECIAL_ROLES:
            result = self.SPECIAL_ROLES[roles]
        else:
            if isinstance(roles, six.string_types):
                roles = [roles]

            if not isinstance(roles, (list, tuple)):
                # TODO(bgaifullin) fix wrong format for roles in tasks.yaml
                # After it will be allowed to raise exception here
                logger.warn(
                    'Wrong roles format, `roles` should be a list or "*": %s',
                    roles
                )
                return []

            result = set()
            for role in roles:
                pattern = NameMatchingPolicy.create(role)
                for node_role, nodes_ids in six.iteritems(self.__mapping):
                    if pattern.match(node_role):
                        result.update(nodes_ids)

        result = list(result)
        # in some cases need only one any node from pool
        # for example if need only one any controller.
        # to distribute load select first node from pool
        if result and policy == consts.NODE_RESOLVE_POLICY.any:
            result = result[0:1]

        logger.debug(
            "Role '%s' and policy '%s' was resolved to: %s",
            roles, policy, result
        )
        return result
