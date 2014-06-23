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

"""
The module is written in pure python (except six) to be more portable
if we decide it to use somewhere else.
"""

import abc
import logging
import os
import six
import shutil


logger = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class Action(object):
    """An action interface.

    The interface is clear and no need to be commented.
    """

    @abc.abstractmethod
    def do(self):
        return NotImplemented

    @abc.abstractmethod
    def undo(self):
        return NotImplemented


class Copy(Action):
    """Copy action provides a way to copy stuff from one place to another.

    The source and destination could be either a file or directory.

    :param from: copy from
    :param to: save to
    """

    def __init__(self, **kwargs):
        self._from = kwargs['from']
        self._to = kwargs['to']
        self._overwrite = kwargs.get('overwrite', True)

    def do(self):
        logger.info('Copying "%s" -> "%s"', self._from, self._to)

        if os.path.isfile(self._from):
            if self._overwrite and os.path.isfile(self._to):
                os.remove(self._to)
            shutil.copy(self._from, self._to)
        else:
            if self._overwrite:
                shutil.rmtree(self._to, ignore_errors=True)
            shutil.copytree(self._from, self._to, symlinks=True)

    def undo(self):
        if not os.path.exists(self._to):
            return

        if os.path.isdir(self._from) and os.path.isdir(self._to):
            logger.info('Removing "%s"', self._to)
            shutil.rmtree(self._to)
        else:
            # since the destination could be a folder even for files we have
            # to introduce this trick for removing exactly file, not a dir.
            dst = self._to
            if os.path.isdir(dst):
                name = os.path.basename(self._from)
                dst = os.path.join(dst, name)

            logger.info('Removing "%s"', dst)
            os.remove(dst)


class CopyFromUpdate(Action):
    """The action extends a regular copy action and adds an additional
    `base_path` argument that'll be prefixed to `from` param.

    :param from: copy from
    :param to: save to
    :param base_path: a path that will be prefixed to from path
    """

    def __init__(self, **kwargs):
        kwargs['from'] = os.path.join(kwargs['base_path'], kwargs['from'])
        self.action = Copy(**kwargs)

    def do(self):
        self.action.do()

    def undo(self):
        self.action.undo()


class Move(Action):
    """Move action provides a way to move stuff from one place to another.

    :param from: a move source
    :param to: a move destination
    """

    def __init__(self, **kwargs):
        self._from = kwargs['from']
        self._to = kwargs['to']

    def do(self):
        logger.info('Moving "%s" -> "%s"', self._from, self._to)
        os.rename(self._from, self._to)

    def undo(self):
        logger.info('Moving "%s" -> "%s"', self._to, self._from)
        os.rename(self._to, self._from)


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

        for action in reversed(self._history):
            action.undo()
        self._history = []
