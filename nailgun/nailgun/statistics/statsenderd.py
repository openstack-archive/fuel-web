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

from random import randint

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
from nailgun.statistics.installation_info import InstallationInfo


class StatsSender(object):

    COLLECTOR_MIRANTIS_SERVER = "collector.mirantis.com"
    COLLECTOR_COMMUNITY_SERVER = "collector.fuel-infra.org"

    def build_collector_url(self, url_template):
        server = self.COLLECTOR_MIRANTIS_SERVER \
            if "mirantis" in settings.VERSION["feature_groups"] \
            else self.COLLECTOR_COMMUNITY_SERVER
        return getattr(settings, url_template).format(collector_server=server)

    def ping_collector(self):
        try:
            resp = requests.get(self.build_collector_url("COLLECTOR_PING_URL"),
                                timeout=settings.COLLECTOR_RESP_TIMEOUT)
            resp.raise_for_status()
            return True
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.RequestException,
                requests.exceptions.HTTPError) as e:
            logger.exception("Collector ping failed: %s", six.text_type(e))
            return False

    def send_data_to_url(self, url, data):
        try:
            headers = {'content-type': 'application/json'}
            resp = requests.post(
                url,
                headers=headers,
                data=jsonutils.dumps(data),
                timeout=settings.COLLECTOR_RESP_TIMEOUT)
            resp.raise_for_status()
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.RequestException,
                requests.exceptions.HTTPError) as e:
            logger.exception(
                "Sending data to collector failed: %s",
                six.text_type(e))
        return resp

    def send_log_serialized(self, records, ids):
        if records:
            logger.info("Send %d records", len(records))
            resp = self.send_data_to_url(
                url=self.build_collector_url("COLLECTOR_ACTION_LOGS_URL"),
                data={"action_logs": records}
            )
            resp_dict = resp.json()
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
                db().query(models.ActionLog).filter(
                    models.ActionLog.id.in_(sent_saved_ids)
                ).update(
                    {"is_sent": True}, synchronize_session=False
                )
                db().commit()
            else:
                logger.error("Unexpected collector answer: %s",
                             six.text_type(resp))

    def send_action_log(self):
        action_log = db().query(models.ActionLog).order_by(
            models.ActionLog.id
        ).filter_by(
            is_sent=False
        ).limit(settings.STATS_SEND_COUNT)
        logger.info("Action log has %d unsent records", action_log.count())

        uid = InstallationInfo().get_master_node_uid()
        offset = 0
        while True:
            log_chunk = action_log.offset(offset)
            records = []
            ids = []
            logger.info("Send records: %s", six.text_type(log_chunk.count()))
            for log_record in log_chunk:
                body = objects.ActionLog.to_dict(log_record)
                record = {
                    'external_id': body['id'],
                    'master_node_uid': uid,
                    'body': body
                }
                records.append(record)
                ids.append(log_record.id)
            self.send_log_serialized(records, ids)
            if log_chunk.count() < settings.STATS_SEND_COUNT:
                break
            offset += settings.STATS_SEND_COUNT

    def send_installation_info(self):
        inst_info = InstallationInfo().get_installation_info()
        resp = self.send_data_to_url(
            url=self.build_collector_url("COLLECTOR_INST_INFO_URL"),
            data={"installation_struct": inst_info}
        )
        if resp.status_code == requests.codes.created and \
                resp.json()["status"] == \
                consts.LOG_CHUNK_SEND_STATUS.ok:
            logger.info("Installation info saved in collector")
        else:
            logger.error("Unexpected collector answer: %s",
                         six.text_type(resp))

    def run(self, *args, **kwargs):

        def dithered(medium):
            return randint(int(medium * 0.9), int(medium * 1.1))

        while True:
            if self.ping_collector():
                self.send_action_log()
                self.send_installation_info()
                time.sleep(dithered(settings.STATS_SEND_INTERVAL))
            else:
                time.sleep(dithered(settings.COLLECTOR_PING_INTERVAL))


def run():
    logger.info("Starting standalone stats sender...")
    try:
        StatsSender().run()
    except (KeyboardInterrupt, SystemExit) as e:
        logger.error("Stats sender exception: %s", six.text_type(e))
    logger.info("Stopping standalone stats sender...")
