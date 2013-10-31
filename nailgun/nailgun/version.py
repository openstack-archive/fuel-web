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


from nailgun.logger import logger
from nailgun.settings import settings


def log_module_version(module_name):
    logger.info("Fuel-Web {0} {1} SHA: {2}\nFuel SHA: {3}".format(
        module_name,
        settings.PRODUCT_VERSION,
        settings.COMMIT_SHA,
        settings.FUEL_COMMIT_SHA
        ))
