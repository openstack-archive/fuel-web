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

import randint
import six
import time

from nailgun import consts
from nailgun.logger import logger
from nailgun.objects import ClusterCollection
from nailgun.settings import settings
from nailgun.statistics import oswl_saver
from nailgun.statistics import utils


def collect_info(self):

    def dithered(medium):
        return randint(int(medium * 0.9), int(medium * 1.1))

    operational_clusters = ClusterCollection.filter_by(
        iterable=None, status="operational").all()

    try:
        for cluster in operational_clusters:
            client_provider = utils.ClientProvider(cluster)
            proxy_for_os_api = utils.get_proxy_for_cluster(cluster)

            with utils.set_proxy(proxy_for_os_api):
                vms_info = utils.get_info_from_os_resource_manager(
                    client_provider.nova.servers,
                    utils.collected_components_attrs[
                        consts.OSWL_RESOURCE_TYPES.vm]
                )

            oswl_saver.oswl_statistics_save(cluster.id,
                                            consts.OSWL_RESOURCE_TYPES.vm,
                                            vms_info)

        time.sleep(
            dithered(settings.OSWL_COLLECTORS_POLLING_INTERVAL["vm"])
        )

    except Exception as e:
        logger.exception("Exception while collecting OS workloads. "
                         "Details:{0}".format(six.text_type(e)))


def run():
    logger.info("Starting OSWL collectors scheduler")
    try:
        while True:
            collect_info()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopping OSWL collectors scheduler")
