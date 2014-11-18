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

from nailgun.api.v1.handlers.base import SingleHandler

from nailgun.db import db

class PingHandler(SingleHandler):
    def GET(self):
        """Ping handler
        :http: * 200 (OK)
               * 500 (Error checking nailgun)
        """
        try:
            db().execute('SELECT 1')
        except:
            raise self.http(500, "Error")
        raise self.http(200, 'ok')
