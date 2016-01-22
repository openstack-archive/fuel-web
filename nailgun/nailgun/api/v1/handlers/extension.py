#    Copyright 2016 Mirantis, Inc.
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

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import content

from nailgun.extensions.base import get_all_extensions


class ExtensionHandler(BaseHandler):

    @content
    def GET(self):
        """:return JSONized list of available extensions

        :http: * 200 (OK)
        """
        return [ext.render() for ext in get_all_extensions()]
