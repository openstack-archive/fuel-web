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
from nailgun.logger import logger
from nailgun.objects import ClusterCollection
from nailgun.settings import settings
from nailgun.statistics import utils


def collect(resource_name):
    try:
        operational_clusters = ClusterCollection.filter_by(
            iterable=None, status=consts.CLUSTER_STATUSES.operational).all()

        for cluster in operational_clusters:
            client_provider = utils.ClientProvider(cluster)
            proxy_for_os_api = utils.get_proxy_for_cluster(cluster)

            with utils.set_proxy(proxy_for_os_api):
                utils.get_info_from_os_resource_manager(
                    client_provider, resource_name)

            # TODO(aroma): add OSWL saver code here

    except Exception as e:
        logger.exception("Exception while collecting OS workloads "
                         "for resource name {0}. Details:{1}"
                         .format(resource_name, six.text_type(e)))


def run():
    resource_name = sys.argv[1]

    logger.info("Starting OSWL collector for {0} resource"
                .format(resource_name))
    try:
        while True:
            collect(resource_name)

            # this prevents from posibility of execution of several collectors
            # to start at the same time
            time.sleep(
                utils.dithered(
                    settings.OSWL_COLLECTORS_POLLING_INTERVAL[resource_name])
            )
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopping OSWL collector for {0} resource"
                    .format(resource_name))
