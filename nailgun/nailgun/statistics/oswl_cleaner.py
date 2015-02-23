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

import time

from nailgun.db import db
from nailgun.logger import logger
from nailgun.objects import OpenStackWorkloadStatsCollection
from nailgun.settings import settings


def run():
    logger.info("Starting OSWL cleaner")
    try:
        while True:
            instances_to_clean = \
                OpenStackWorkloadStatsCollection.get_ready_to_delete()
            instances_to_clean.delete(synchronize_session=False)

            db().commit()

            time.sleep(settings.OSWL_CLEANER_SLEEP_INTERVAL)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopping OSWL cleaner")
