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


class UnresolvableConflict(ValueError):
    pass


def is_text(t):
    return isinstance(t, six.text_type) or isinstance(t, six.string_types)


@six.add_metaclass(abc.ABCMeta)
class MergePolicy(object):
    """class that provides functional
    to plugins attributes with origin.
    """

    @abc.abstractmethod
    def apply_patch(self, target, patch):
        """applies patch to target."""


class NetworkRoleMergePolicy(MergePolicy):
    def __init__(self):
        self.rules = {'vip': NetworkRoleMergePolicy._patch_vips}

    @staticmethod
    def _patch_vips(target, patch):
        """patches VIP attribute for network role."""
        seen = set(x['name'] for x in target)
        for v in patch:
            if v['name'] not in seen:
                seen.add((v['name']))
                target.append(v)
        return target

    def apply_patch(self, target, patch):
        """try to apply patch to target,
        resolve conflicts according to knowledge about fields,
        that can be merged.
        """

        target_props = target['properties']
        patch_props = patch['properties']

        conflict = set(target_props) & set(patch_props)
        mergeable = set(self.rules)

        # exclude fields that has same value
        for k in (conflict - mergeable):
            if target_props[k] != patch_props[k]:
                raise UnresolvableConflict(
                    "Cannot apply patch for attribute {0}: conflict"
                    .format(k)
                )
            conflict.remove(k)

        if conflict <= mergeable:
            for k in conflict:
                try:
                    target_props[k] = self.rules[k](
                        target_props[k],
                        patch_props[k]
                    )
                except Exception as e:
                    raise UnresolvableConflict(
                        "Cannot apply patch for attribute {0}: {1}"
                        .format(k, e)
                    )
