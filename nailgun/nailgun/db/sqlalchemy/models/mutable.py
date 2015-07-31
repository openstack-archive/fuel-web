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

from sqlalchemy.ext.mutable import Mutable


class MutableList(Mutable, list):
    # TODO(fzhadaev): delete this class after it will be
    #                 implemented in sqlalchemy lib.
    # https://bitbucket.org/zzzeek/sqlalchemy/issues/3297

    @classmethod
    def coerce(cls, key, value):
        """Convert plain lists to MutableList."""

        if not isinstance(value, MutableList):
            if isinstance(value, list):
                return MutableList(value)

            # this call will raise ValueError
            return Mutable.coerce(key, value)
        else:
            return value

    def __setitem__(self, key, value):
        """Detect list set events and emit change events."""

        list.__setitem__(self, key, value)
        self.changed()

    def __delitem__(self, key):
        """Detect list del events and emit change events."""

        list.__delitem__(self, key)
        self.changed()

    def append(self, value):
        list.append(self, value)
        self.changed()

    def extend(self, iterable):
        list.extend(self, iterable)
        self.changed()

    def __getstate__(self):
        return list(self)

    def __setstate__(self, state):
        self[:] = state
