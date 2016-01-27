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
import six

from nailgun.errors import errors


@six.add_metaclass(abc.ABCMeta)
class MergePolicy(object):
    """Policy to merge attributes of plugins."""

    @abc.abstractmethod
    def apply_patch(self, target, patch):
        """Applies patch to the target.

        :param target: the origin object, the target can be modified.
        :param patch: the modifications for merging with original
        :return: the patched object.
        """


class NetworkRoleMergePolicy(MergePolicy):
    """Policy for merging network roles."""

    def __init__(self):
        self.rules = {'vip': NetworkRoleMergePolicy._patch_vips}

    @staticmethod
    def _patch_vips(target, patch):
        """Patches VIP attribute for network role.

        :param: target: the origin VIPs.
        :type target: list
        :param patch: the VIPs, that will be added to origin
        :type patch: list
        :return: the patched VIPs
        """
        seen = dict((vip['name'], vip) for vip in target)

        if len(patch) == 0:
            return []

        for vip in patch:
            if vip['name'] in seen:
                if vip != seen[vip['name']]:
                    raise ValueError(
                        "VIP '{0}' conflicts with existing one"
                        .format(vip['name'])
                    )
            else:
                seen[vip['name']] = vip
                target.append(vip)

        return target

    def apply_patch(self, target, patch):
        """Tries to apply patch to the target.

        Conflicts will be resolved according to the
        predefined rules.

        :param target: the origin network role
        :type target: dict
        :param patch: the modifications for merging with origin
        :type patch: dict
        :raises: errors.UnresolvableConflict
        """

        target_props = target['properties']
        patch_props = patch['properties']

        conflict = set(target_props) & set(patch_props)
        mergeable = set(self.rules)

        # Exclude fields that has same value
        for name in (conflict - mergeable):
            if target_props[name] != patch_props[name]:
                raise errors.UnresolvableConflict(
                    "Cannot apply patch for attribute {0}: conflict"
                    .format(name)
                )
            conflict.remove(name)

        for name in conflict:
            try:
                target_props[name] = self.rules[name](
                    target_props[name],
                    patch_props[name]
                )
            except Exception as e:
                raise errors.UnresolvableConflict(
                    "Cannot apply patch for attribute {0}: {1}"
                    .format(name, e)
                )
