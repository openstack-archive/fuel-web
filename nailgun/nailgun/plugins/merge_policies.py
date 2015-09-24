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
        """Applies patch to the target."""


class NetworkRoleMergePolicy(MergePolicy):
    def __init__(self):
        self.rules = {'vip': NetworkRoleMergePolicy._patch_vips}

    @staticmethod
    def _patch_vips(target, patch):
        """Patches VIP attribute for network role.

        :return: the patched target
        """
        seen = set(x['name'] for x in target)
        for v in patch:
            if v['name'] not in seen:
                seen.add(v['name'])
                target.append(v)
        return target

    def apply_patch(self, target, patch):
        """Tries to apply patch to target.

        Conflicts will be resolved according to the
        predefined rules.
        """

        target_props = target['properties']
        patch_props = patch['properties']

        conflict = set(target_props) & set(patch_props)
        mergeable = set(self.rules)

        # Exclude fields that has same value
        for k in (conflict - mergeable):
            if target_props[k] != patch_props[k]:
                raise errors.UnresolvableConflict(
                    "Cannot apply patch for attribute {0}: conflict"
                    .format(k)
                )
            conflict.remove(k)

        for k in conflict:
            try:
                target_props[k] = self.rules[k](
                    target_props[k],
                    patch_props[k]
                )
            except Exception as e:
                raise errors.UnresolvableConflict(
                    "Cannot apply patch for attribute {0}: {1}"
                    .format(k, e)
                )
