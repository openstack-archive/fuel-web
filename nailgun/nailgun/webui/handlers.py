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

import jinja2
import os.path

from nailgun.settings import settings


class IndexHandler(object):
    def GET(self):
        tpl_path = os.path.join(settings.TEMPLATE_DIR, 'index.html')
        with open(tpl_path, 'r') as f:
            tpl = jinja2.Template(f.read())
            return tpl.render()
