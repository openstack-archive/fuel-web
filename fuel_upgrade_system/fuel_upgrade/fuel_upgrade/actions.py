# -*- coding: utf-8 -*-

#    Copyright 2014 Mirantis, Inc.
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
import logging
import os
import six

from fuel_upgrade.utils import copy, remove, rename


logger = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class Action(object):
    """An action interface.

    The interface is clear and no need to be commented.
    """

    @abc.abstractmethod
    def do(self):
        """Performs an action.
        """

    @abc.abstractmethod
    def undo(self):
        """Rollbacks an action.
        """


class Copy(Action):
    """Copy action provides a way to copy stuff from one place to another.

    The source and destination could be either a file or directory.

    :param from: copy from
    :param to: copy to
    :param overwrite: overwrite a destination if True
    :param symlinks: resolve symlinks if True
    """

    def __init__(self, **kwargs):
        self._from = kwargs['from']
        self._to = kwargs['to']
        self._overwrite = kwargs.get('overwrite', True)
        self._symlinks = kwargs.get('symlinks', True)

    def do(self):
        copy(self._from, self._to, self._overwrite, self._symlinks)

    def undo(self):
        # destination should be a path/to/file in case source was a file
        destination = self._to
        if not os.path.isdir(self._from) and os.path.isdir(self._to):
            basename = os.path.basename(self._from)
            destination = os.path.join(self._to, basename)

        # do nothing if destination doesn't exist
        remove(destination, ignore_errors=True)


class CopyFromUpdate(Action):
    """The action extends a regular copy action and adds an additional
    `base_path` argument that'll be prefixed to `from` param.

    :param from: copy from
    :param to: save to
    :param overwrite: overwrite a destination if True
    :param symlinks: resolve symlinks if True
    :param base_path: a path that will be prefixed to from path
    """

    def __init__(self, **kwargs):
        kwargs['from'] = os.path.join(kwargs['base_path'], kwargs['from'])
        self.copy = Copy(**kwargs)

    def do(self):
        self.copy.do()

    def undo(self):
        self.copy.undo()


class Move(Action):
    """Move action provides a way to move stuff from one place to another.

    :param from: a move source
    :param to: a move destination
    :param overwrite: overwrite a destination if True
    """

    def __init__(self, **kwargs):
        self._from = kwargs['from']
        self._to = kwargs['to']
        self._overwrite = kwargs.get('overwrite', True)

    def do(self):
        rename(self._from, self._to, self._overwrite)

    def undo(self):
        rename(self._to, self._from, self._overwrite)


class ActionManager(object):
    """The action manager is designed to manage actions, run it or
    rollback based on action description.

    :param actions: a list with action descriptions
    :param context: a dict with some context that's passed to actions
    """

    #: a list of supported actions
    supported_actions = {
        'copy': Copy,
        'copy_from_update': CopyFromUpdate,
        'move': Move,
    }

    def __init__(self, actions, **context):
        #: a list of actions to execute
        self._actions = []

        #: a list of executed actions (we need it to rollback feature)
        self._history = []

        # convert some input action description to class instances
        for action in actions:
            kwargs = dict(action, **context)

            action_class = self.supported_actions[action['name']]
            self._actions.append(action_class(**kwargs))

    def do(self):
        """Performs actions saving in history."""

        for action in self._actions:
            action.do()
            self._history.append(action)

    def undo(self):
        """Rollbacks completed actions."""

        while self._history:
            action = self._history.pop()
            action.undo()
