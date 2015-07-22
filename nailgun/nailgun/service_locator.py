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

# Default mappings which are loaded into nailgun.service_locater.ServiceLocator
DEFAULT_MAPPINGS = {
    'nailgun.objects.Cluster': 'nailgun/objects/cluster.py',
    'nailgun.objects.Node': 'nailgun/objects/node.py'
}


class ServiceLocator(object):

    # 'class_name': 'path_to_class'
    _classes = DEFAULT_MAPPINGS

    @classmethod
    def add_class(cls, class_name, class_path):
        cls._classes[class_name] = class_path

    @classmethod
    def get_class(cls, class_name):
        return cls._classes.get(class_name)

    @classmethod
    def fabricate(cls, class_name, *args, **kwargs):

        class_name = cls._classes.get(class_name)
        if class_name:
            path, class_name = class_name.rsplit('.', 1)

            try:
                module = importlib.import_module(path)
                return getattr(module, class_name)(*args, **kwargs)
            except (ImportError, AttributeError) as err:
                raise Exception(err)

        raise Exception(u"Class {0} not found in mappings".format(class_name))

    @classmethod
    def remove(cls, class_name):
        if cls._classes.get(class_name):
            del cls._classes[class_names]
