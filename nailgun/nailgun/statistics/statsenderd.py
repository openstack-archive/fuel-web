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
import urllib3

from oslo_serialization import jsonutils

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.logger import logger
from nailgun import objects
from nailgun.settings import settings
from nailgun.statistics.fuel_statistics.installation_info \
    import InstallationInfo
from nailgun.statistics.utils import dithered


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
        except (urllib3.exceptions.DecodeError,
                urllib3.exceptions.ProxyError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.TooManyRedirects,
                requests.exceptions.HTTPError) as e:
            logger.error("Collector ping failed: %s", type(e).__name__)
        except Exception as e:
            logger.exception("Collector ping failed: %s", six.text_type(e))
        return False

    def send_data_to_url(self, url, data):
        resp = None
        try:
            headers = {
                'content-type': 'application/json',
                'master-node-uid': InstallationInfo().get_master_node_uid()
            }
            resp = requests.post(
                url,
                headers=headers,
                data=jsonutils.dumps(data),
                timeout=settings.COLLECTOR_RESP_TIMEOUT)
        except (urllib3.exceptions.DecodeError,
                urllib3.exceptions.ProxyError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.TooManyRedirects) as e:
            logger.error("Sending data to collector failed: %s",
                         type(e).__name__)
        except Exception as e:
            logger.exception(
                "Sending data to collector failed: %s", six.text_type(e))
        return resp

    def is_status_acceptable(
            self, resp_status_code, resp_status,
            codes=(requests.codes.created, requests.codes.ok)
    ):
        return (resp_status_code in codes and
                resp_status == consts.LOG_CHUNK_SEND_STATUS.ok)

    def send_log_serialized(self, records, ids):
        if records:
            logger.info("Send %d action logs records", len(records))
            resp = self.send_data_to_url(
                url=self.build_collector_url("COLLECTOR_ACTION_LOGS_URL"),
                data={"action_logs": records}
            )
            resp_dict = resp.json()
            if self.is_status_acceptable(resp.status_code,
                                         resp_dict["status"]):
                records_resp = resp_dict["action_logs"]
                saved_ids = set()
                failed_ids = set()
                skipped_ids = set()
                for record in records_resp:
                    if record["status"] == \
                            consts.LOG_RECORD_SEND_STATUS.failed:
                        failed_ids.add(record["external_id"])
                    elif record["status"] == \
                            consts.LOG_RECORD_SEND_STATUS.skipped:
                        skipped_ids.add(record["external_id"])
                    else:
                        saved_ids.add(record["external_id"])
                sent_saved_ids = set(saved_ids) & set(ids)
                logger.info("Action logs records saved: %s, failed: %s, "
                            "skipped: %s",
                            six.text_type(list(sent_saved_ids)),
                            six.text_type(list(failed_ids)),
                            six.text_type(list(skipped_ids)))
                if sent_saved_ids:
                    db().query(models.ActionLog).filter(
                        models.ActionLog.id.in_(sent_saved_ids)
                    ).update(
                        {"is_sent": True}, synchronize_session=False
                    )
                    db().commit()
            else:
                logger.error("Unexpected collector answer: %s",
                             six.text_type(resp.text))

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
        logger.info("Sending installation structure info")
        inst_info = InstallationInfo().get_installation_info()
        resp = self.send_data_to_url(
            url=self.build_collector_url("COLLECTOR_INST_INFO_URL"),
            data={"installation_structure": inst_info}
        )
        resp_dict = resp.json()
        if self.is_status_acceptable(resp.status_code, resp_dict["status"]):
            logger.info("Installation structure info saved in collector")
        else:
            logger.error("Unexpected collector answer: %s",
                         six.text_type(resp.text))

    def send_oswl_serialized(self, rec_data, ids):
        if rec_data:
            resp = self.send_data_to_url(
                url=self.build_collector_url("COLLECTOR_OSWL_INFO_URL"),
                data={"oswl_stats": rec_data}
            )
            resp_dict = resp.json()
            if self.is_status_acceptable(resp.status_code,
                                         resp_dict["status"]):
                records_resp = resp_dict["oswl_stats"]
                status_failed = consts.LOG_RECORD_SEND_STATUS.failed
                saved_ids = set(r["id"] for r in records_resp
                                if r["status"] != status_failed)
                failed_ids = set(r["id"] for r in records_resp
                                 if r["status"] == status_failed)
                sent_saved_ids = set(saved_ids) & set(ids)
                logger.info("OSWL info records saved: %s, failed: %s",
                            six.text_type(list(sent_saved_ids)),
                            six.text_type(list(failed_ids)))
                if sent_saved_ids:
                    db().query(models.OpenStackWorkloadStats).filter(
                        models.OpenStackWorkloadStats.id.in_(sent_saved_ids)
                    ).update(
                        {"is_sent": True}, synchronize_session=False
                    )
                    db().commit()
            else:
                logger.error("Unexpected collector answer: %s",
                             six.text_type(resp.text))

    def send_oswl_info(self):
        logger.info("Sending OpenStack workload info")
        oswl_data = objects.OpenStackWorkloadStatsCollection\
            .get_ready_to_send().limit(settings.OSWL_SEND_COUNT)
        logger.info("Pending records count: %s",
                    six.text_type(oswl_data.count()))
        uid = InstallationInfo().get_master_node_uid()
        offset = 0
        records = []
        ids = []
        while True:
            data_chunk = oswl_data.offset(offset)
            for rec in data_chunk:
                rec_data = objects.OpenStackWorkloadStats.to_dict(rec)
                rec_data['master_node_uid'] = uid
                rec_data['created_date'] = rec_data['created_date'].isoformat()
                rec_data['updated_time'] = rec_data['updated_time'].isoformat()
                records.append(rec_data)
                ids.append(rec_data['id'])
            self.send_oswl_serialized(records, ids)
            if data_chunk.count() < settings.OSWL_SEND_COUNT:
                break
            offset += settings.OSWL_SEND_COUNT

        logger.info("OpenStack workload info is sent")

    def send_stats_once(self):
        try:
            if objects.MasterNodeSettings.must_send_stats():
                if self.ping_collector():
                    self.send_action_log()
                    self.send_installation_info()
                    self.send_oswl_info()
                    time.sleep(dithered(settings.STATS_SEND_INTERVAL))
                else:
                    time.sleep(dithered(settings.COLLECTOR_PING_INTERVAL))
            else:
                time.sleep(dithered(settings.STATS_ENABLE_CHECK_INTERVAL))
        except Exception as e:
            logger.error("Stats sender exception: %s", six.text_type(e))
            time.sleep(dithered(settings.COLLECTOR_PING_INTERVAL))
        finally:
            db.remove()


def run():
    logger.info("Starting standalone stats sender...")
    try:
        while True:
            StatsSender().send_stats_once()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopping standalone stats sender...")
