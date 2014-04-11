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

import os

from nose.plugins import Plugin

from nailgun.settings import settings


class DbPlugin(Plugin):

        name = 'db'
        enabled = True

        def configure(self, options, conf):
            db_name = os.environ.get('TEST_NAILGUN_DB')
            if db_name:
                settings.DATABASE['name'] = db_name
