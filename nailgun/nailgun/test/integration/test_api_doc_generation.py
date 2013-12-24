# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

import imp
import os

from inspect import getmembers
from inspect import isclass

from nailgun.api.urls.v1 import urls
from nailgun.autoapidoc import SampleGenerator
from nailgun.test.base import BaseIntegrationTest


class TestAPIDocGeneration(BaseIntegrationTest):

    def get_handlers_list(self):
        return []

    def load_from_file(self, filepath):
        mod_name, file_ext = os.path.splitext(os.path.split(filepath)[-1])
        if file_ext.lower() == '.py':
            py_mod = imp.load_source(mod_name, filepath)
        #elif file_ext.lower() == '.pyc':
        #    py_mod = imp.load_compiled(mod_name, filepath)
        else:
            return []

        class_list = [obj[1] for obj in getmembers(py_mod)
                      if isclass(obj[1]) and obj[0] in urls[1::2]]

        return class_list

    def load_from_path(self, startPath):
        r = []
        d = os.path.abspath(startPath)
        if os.path.exists(d) and os.path.isdir(d):
            for root, dirs, files in os.walk(d):
                for f in files:
                    r.extend(self.load_from_file(root + '/' + f))
        return r

    def test_url_generator(self):
        path = os.path.dirname(os.path.realpath(__file__))
        path = ('/'.join(path.split('/')[:-2])) + "/api/handlers/"
        modules = self.load_from_path(path)
        names = set()
        unique_modules = []
        urls_ = []
        for m in modules:
            if m.__name__ in names:
                continue
            names.add(m.__name__)
            unique_modules.append(m)
            url = SampleGenerator.generate_handler_url_doc(m)
            self.assertNotEqual(url, "URL: **Not exposed**")
            self.assertTrue(SampleGenerator._ishandler(m))
            urls_.append(url)
        self.assertEqual(len(urls_), len(urls) / 2)
        self.assertEqual(len(unique_modules), len(urls) / 2)
