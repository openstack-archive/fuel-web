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

import web

from nailgun.fake_keystone.v2_handlers \
    import EndpointsHandler as V2EndpointsHandler
from nailgun.fake_keystone.v2_handlers \
    import ServicesHandler as V2ServicesHandler
from nailgun.fake_keystone.v2_handlers \
    import TokensHandler as V2TokensHandler
from nailgun.fake_keystone.v2_handlers \
    import VersionHandler as V2VersionHandler

from nailgun.fake_keystone.v3_handlers \
    import TokensHandler as V3TokensHandler
from nailgun.fake_keystone.v3_handlers \
    import VersionHandler as V3VersionHandler

urls = (
    r"/v2.0/?$", V2VersionHandler,
    r"/v2.0/tokens/?$", V2TokensHandler,
    r"/v2.0/OS-KSADM/services/?$", V2ServicesHandler,
    r"/v2.0/endpoints/?$", V2EndpointsHandler,
    r"/v3/?$", V3VersionHandler,
    r"/v3/auth/tokens/?$", V3TokensHandler,
)

_locals = locals()


def app():
    return web.application(urls, _locals)
