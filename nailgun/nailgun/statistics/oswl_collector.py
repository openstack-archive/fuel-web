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

import six
import sys
import time

from nailgun import consts
from nailgun.db import db
from nailgun.logger import logger
from nailgun.objects import ClusterCollection
from nailgun.settings import settings
from nailgun.statistics import utils
from nailgun.statistics.oswl_saver import oswl_statistics_save


def collect(resource_type):
    try:
        operational_clusters = ClusterCollection.filter_by(
            iterable=None, status=consts.CLUSTER_STATUSES.operational).all()

        for cluster in operational_clusters:
            client_provider = utils.ClientProvider(cluster)
            proxy_for_os_api = utils.get_proxy_for_cluster(cluster)

            with utils.set_proxy(proxy_for_os_api):
                data = utils.get_info_from_os_resource_manager(
                    client_provider, resource_type)
                oswl_statistics_save(cluster.id, resource_type, data)
        db.commit()

    except Exception as e:
        logger.exception("Exception while collecting OS workloads "
                         "for resource name {0}. Details: {1}"
                         .format(resource_type, six.text_type(e)))
    finally:
        db.remove()


def run():
    resource_type = sys.argv[1]
    poll_interval = settings.OSWL_COLLECTORS_POLLING_INTERVAL[resource_type]
    logger.info("Starting OSWL collector for {0} resource"
                .format(resource_type))
    try:
        while True:
            collect(resource_type)
            time.sleep(poll_interval)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopping OSWL collector for {0} resource"
                    .format(resource_type))
