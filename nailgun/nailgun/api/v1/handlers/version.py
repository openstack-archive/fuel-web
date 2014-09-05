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

"""
Product info handlers
"""

import glob
import os

import yaml

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import content_json
from nailgun.logger import logger
from nailgun.settings import settings


class VersionHandler(BaseHandler):
    """Version info handler
    """

    release_versions = "/etc/fuel/release_versions/*.yaml"

    @content_json
    def GET(self):
        """:returns: FUEL/FUELWeb commit SHA, release version.
        :http: * 200 (OK)
        """
        version = settings.VERSION
        method = settings.AUTH['AUTHENTICATION_METHOD']
        version['auth_required'] = method in ['fake', 'keystone']

        version['release_versions'] = {}
        for fl in glob.glob(self.release_versions):
            with open(fl, "r") as release_yaml:
                try:
                    version['release_versions'][
                        os.path.splitext(os.path.basename(fl))[0]
                    ] = yaml.load(
                        release_yaml.read()
                    )
                except Exception as exc:
                    logger.warning(
                        u"Failed to load release version "
                        "info from '{0}': {1}".format(
                            fl,
                            unicode(exc)
                        )
                    )

        return version
