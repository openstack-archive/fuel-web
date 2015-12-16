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
from nailgun.objects import MasterNodeSettings
from nailgun.objects import OpenStackWorkloadStatsCollection
from nailgun.settings import settings
from nailgun.statistics import errors
from nailgun.statistics.oswl import helpers
from nailgun.statistics.oswl.saver import oswl_statistics_save
from nailgun.statistics import utils


def collect(resource_type):
    try:
        operational_clusters = ClusterCollection.filter_by(
            iterable=None, status=consts.CLUSTER_STATUSES.operational).all()
        error_clusters = ClusterCollection.filter_by(
            iterable=None, status=consts.CLUSTER_STATUSES.error).all()

        all_envs_last_recs = \
            OpenStackWorkloadStatsCollection.get_last_by_resource_type(
                resource_type)
        ready_or_error_ids = set([c.id for c in operational_clusters] +
                                 [c.id for c in error_clusters])
        envs_ids_to_clear = set(r.cluster_id for r in all_envs_last_recs) - \
            ready_or_error_ids
        # Clear current resource data for unavailable clusters.
        # Current OSWL data is cleared for those clusters which status is not
        # 'operational' nor 'error' or when cluster was removed. Data is
        # cleared for cluster only if it was updated recently (today or
        # yesterday). While this collector is running with interval much
        # smaller than one day it should not miss any unavailable cluster.
        for id in envs_ids_to_clear:
            oswl_statistics_save(id, resource_type, [])

        # Collect current OSWL data and update data in DB
        for cluster in operational_clusters:
            try:
                client_provider = helpers.ClientProvider(cluster)
                proxy_for_os_api = utils.get_proxy_for_cluster(cluster)
                version_info = utils.get_version_info(cluster)

                with utils.set_proxy(proxy_for_os_api):
                    data = helpers.get_info_from_os_resource_manager(
                        client_provider, resource_type)
                    oswl_statistics_save(cluster.id, resource_type, data,
                                         version_info=version_info)

            except errors.StatsException as e:
                logger.error("Cannot collect OSWL resource {0} for cluster "
                             "with id {1}. Details: {2}."
                             .format(resource_type,
                                     cluster.id,
                                     six.text_type(e))
                             )
            except Exception as e:
                logger.exception("Error while collecting OSWL resource {0} "
                                 "for cluster with id {1}. Details: {2}."
                                 .format(resource_type,
                                         cluster.id,
                                         six.text_type(e))
                                 )

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
            if MasterNodeSettings.must_send_stats():
                collect(resource_type)

            time.sleep(poll_interval)

    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopping OSWL collector for {0} resource"
                    .format(resource_type))
