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

import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

import requests

import six

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
#from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.objects.serializers.base import BasicSerializer
from nailgun.openstack.common import jsonutils
from nailgun.settings import settings


class StatsSender():

    fields = ("id", "actor_id", "action_group", "action_name")

    def ping_collector(self):
        try:
            resp = requests.get(settings.COLLECTOR_PING_URL, timeout=5)
            return resp.status_code == requests.codes.ok
        except requests.exceptions as e:
            logger.error("Collector ping exception: %s", six.text_type(e))
            return False

    def send_action_log(self):

        def send_serialized():
            if records:
                logger.info("Send %d records", len(records))
                resp = None
                try:
                    resp = requests.post(settings.COLLECTOR_STORE_URL,
                                         jsonutils.dumps(records))
                except requests.exceptions as e:
                    logger.error("Collector store exception: %s",
                                 six.text_type(e))
                if resp and resp.status_code == requests.codes.ok:
                    received_ids = resp.text['']
                    ids_sent = set(received_ids) & set(ids)
                    logger.info("Records are sent: %s",
                                six.text_type(ids_sent))
                    # db().query(models.ActionLog).filter(
                    #     models.ActionLog.id.in_(ids_sent)
                    # ).update(
                    #     {"is_sent": True}, synchronize_session=False
                    # )
                    # db().commit()

        action_log = db().query(models.ActionLog).order_by(
            models.ActionLog.id
        ).filter_by(
            is_sent=False
        )
        records = []
        ids = []
        logger.info("Action log has %d unsent records", action_log.count())
        for log_record in action_log:
            # send by consts.STATS_SEND_COUNT log records per request
            if len(records) < consts.STATS_SEND_COUNT:
                records.append(BasicSerializer.serialize(
                    instance=log_record,
                    fields=self.fields
                ))
                ids.append(log_record.id)
            else:
                send_serialized()
                records = []
                ids = []
        send_serialized()

    def run(self, *args, **kwargs):
        while True:
            if True:  # self.ping_collector():
                self.send_action_log()
                time.sleep(consts.STATS_SEND_INTERVAL)
            else:
                time.sleep(consts.STATS_PING_INTERVAL)


def run():
    logger.info("Starting standalone stats sender...")
    try:
        StatsSender().run()
    except (KeyboardInterrupt, SystemExit) as e:
        logger.error("Stats sender exception: %s", six.text_type(e))
    logger.info("Stopping standalone stats sender...")
