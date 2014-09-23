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

import requests

import six

import time

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.logger import logger
from nailgun import objects
from nailgun.openstack.common import jsonutils
from nailgun.settings import settings


class StatsSender():

    def ping_collector(self):
        try:
            resp = requests.get(settings.COLLECTOR_PING_URL, timeout=5)
            resp.raise_for_status()
            return True
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.RequestException,
                requests.exceptions.HTTPError) as e:
            logger.exception("Collector ping failed: %s", six.text_type(e))
            return False

    def send_action_log(self):

        def send_serialized():
            if records:
                logger.info("Send %d records", len(records))
                try:
                    req_body = {"action_logs": records}
                    headers = {'content-type': 'application/json'}
                    resp = requests.post(settings.COLLECTOR_STORE_URL,
                                         headers=headers,
                                         data=jsonutils.dumps(req_body))
                    resp.raise_for_status()
                except (requests.exceptions.ConnectionError,
                        requests.exceptions.Timeout,
                        requests.exceptions.RequestException,
                        requests.exceptions.HTTPError) as e:
                    logger.exception(
                        "Action logs sending to collector failed: %s",
                        six.text_type(e))
                else:
                    resp_dict = dict(resp.json())
                    if resp.status_code == requests.codes.created and \
                            resp_dict["status"] == \
                            consts.LOG_CHUNK_SEND_STATUS.ok:
                        records_resp = resp_dict["action_logs"]
                        saved_ids = set()
                        failed_ids = set()
                        for record in records_resp:
                            if record["status"] == \
                                    consts.LOG_RECORD_SEND_STATUS.failed:
                                failed_ids.add(record["external_id"])
                            else:
                                saved_ids.add(record["external_id"])
                        sent_saved_ids = set(saved_ids) & set(ids)
                        logger.info("Records saved: %s, failed: %s",
                                    six.text_type(list(sent_saved_ids)),
                                    six.text_type(list(failed_ids)))
                        # db().query(models.ActionLog).filter(
                        #     models.ActionLog.id.in_(sent_saved_ids)
                        # ).update(
                        #     {"is_sent": True}, synchronize_session=False
                        # )
                        # db().commit()
                    else:
                        logger.error("Unexpected collector answer: %s",
                                     six.text_type(resp))

        action_log = db().query(models.ActionLog).order_by(
            models.ActionLog.id
        ).filter_by(
            is_sent=False
        )
        records = []
        ids = []
        logger.info("Action log has %d unsent records", action_log.count())
        for log_record in action_log:
            # send by settings.STATS_SEND_COUNT log records per request
            if len(records) < settings.STATS_SEND_COUNT:
                body = objects.ActionLog.to_dict(log_record)
                record = {
                    'external_id': body['id'],
                    'node_aid': 'test_aid',
                    'body': body
                }
                records.append(record)
                ids.append(log_record.id)
            if len(records) == settings.STATS_SEND_COUNT:
                send_serialized()
                records = []
                ids = []
        send_serialized()

    def run(self, *args, **kwargs):
        while True:
            if self.ping_collector():
                self.send_action_log()
                time.sleep(settings.STATS_SEND_INTERVAL)
            else:
                time.sleep(settings.STATS_PING_INTERVAL)


def run():
    logger.info("Starting standalone stats sender...")
    try:
        StatsSender().run()
    except (KeyboardInterrupt, SystemExit) as e:
        logger.error("Stats sender exception: %s", six.text_type(e))
    logger.info("Stopping standalone stats sender...")
