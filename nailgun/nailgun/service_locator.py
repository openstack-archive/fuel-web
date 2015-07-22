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

import importlib


class ServiceLocator(object):

    _classes = dict()

    def __init__(self, mappings):
        self._classes = mappings

    def __getattr__(self, class_name):
        module_namespace = self._classes.get(class_name)
        module = importlib.import_module(module_namespace)

        return getattr(module, class_name)
