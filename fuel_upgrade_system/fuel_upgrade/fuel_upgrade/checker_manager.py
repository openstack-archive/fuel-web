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


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


class CheckerManager(object):

    def __init__(self, checkers_engines_mapping, upgraders, config):
        self.upgraders = upgraders
        self._checkers_engines_mapping = checkers_engines_mapping
        required_free_spaces = [
            upgarde.required_free_space
            for upgarde in self.upgraders]
        self.context = AttrDict(
            config=config,
            required_free_spaces=required_free_spaces)

    def check(self):
        for checker in self._checkers:
            checker.check()

    @property
    def _checkers(self):
        checkers_classes = []
        for engine, checkers in self._checkers_engines_mapping.items():
            if self._is_engine_enabled(engine):
                checkers_classes.extend(checkers)

        return [checker(self.context) for checker in set(checkers_classes)]

    def _is_engine_enabled(self, engine_class):
        """Checks if engine in the list

        :param list engines_list: list of engines
        :param engine_class: engine class

        :returns: True if engine in the list
                  False if engine not in the list
        """
        engines = filter(
            lambda engine: isinstance(engine, engine_class),
            self.upgraders)
        if engines:
            return True

        return False
