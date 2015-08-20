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

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import content
from nailgun.errors import errors
from nailgun import objects


# The sole purpose of this endpoint is to help fuel-nailgun-agent
# understand if Master node was reinstalled. Since fuel-nailgun-agent
# does not have Nailgun credentials, the endpoint must remain public.
class MasterNodeUidHandler(BaseHandler):

    single = objects.MasterNodeSettings
    not_found_error = "Master Node UID is not found in DB"

    @content
    def GET(self):
        """Get singleton object from DB
        :http: * 200 (OK)
               * 404 (Object not found in DB)
        """

        try:
            instance = self.single.get_one(fail_if_not_found=True)
        except errors.ObjectNotFound:
            raise self.http(404, self.not_found_error)

        return instance['master_node_uid']
