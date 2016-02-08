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

import datetime
import json
from mock import Mock
from mock import patch
import requests
import urllib3

from nailgun.test.base import BaseTestCase

from nailgun import consts
from nailgun.objects import Cluster
from nailgun.objects import MasterNodeSettings
from nailgun.objects import OpenStackWorkloadStats
from nailgun.settings import settings
from nailgun.statistics.statsenderd import StatsSender

FEATURE_EXPERIMENTAL = {'feature_groups': ['experimental']}


class TestStatisticsSender(BaseTestCase):

    def check_collector_urls(self, server):
        self.assertEqual(
            StatsSender().build_collector_url("COLLECTOR_ACTION_LOGS_URL"),
            settings.COLLECTOR_ACTION_LOGS_URL.format(collector_server=server)
        )
        self.assertEqual(
            StatsSender().build_collector_url("COLLECTOR_INST_INFO_URL"),
            settings.COLLECTOR_INST_INFO_URL.format(collector_server=server)
        )
        self.assertEqual(
            StatsSender().build_collector_url("COLLECTOR_OSWL_INFO_URL"),
            settings.COLLECTOR_OSWL_INFO_URL.format(collector_server=server)
        )
        self.assertEqual(
            StatsSender().build_collector_url("COLLECTOR_PING_URL"),
            settings.COLLECTOR_PING_URL.format(collector_server=server)
        )

    @patch.dict('nailgun.settings.settings.VERSION', FEATURE_EXPERIMENTAL)
    def test_community_collector_urls(self):
        self.check_collector_urls(StatsSender.COLLECTOR_COMMUNITY_SERVER)

    @patch('nailgun.statistics.statsenderd.requests.get')
    def test_ping_ok(self, requests_get):
        requests_get.return_value = Mock(status_code=200)
        sender = StatsSender()

        self.assertTrue(sender.ping_collector())
        requests_get.assert_called_once_with(
            sender.build_collector_url("COLLECTOR_PING_URL"),
            timeout=settings.COLLECTOR_RESP_TIMEOUT)

    @patch('nailgun.statistics.statsenderd.requests.get')
    @patch('nailgun.statistics.statsenderd.logger.error')
    def test_ping_failed_on_connection_errors(self, log_error, requests_get):
        except_types = (
            urllib3.exceptions.DecodeError,
            urllib3.exceptions.ProxyError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.TooManyRedirects,
            requests.exceptions.HTTPError)

        for except_ in except_types:
            requests_get.side_effect = except_()
            self.assertFalse(StatsSender().ping_collector())
            log_error.assert_called_with("Collector ping failed: %s",
                                         type(except_()).__name__)

    @patch('nailgun.statistics.statsenderd.requests.get')
    @patch('nailgun.statistics.statsenderd.logger.exception')
    def test_ping_failed_on_exception(self, log_exception, requests_get):
        requests_get.side_effect = Exception("custom")

        self.assertFalse(StatsSender().ping_collector())
        log_exception.assert_called_once_with(
            "Collector ping failed: %s", "custom")

    @patch('nailgun.statistics.statsenderd.requests.post')
    def test_send_ok(self, requests_post):
        requests_post.return_value = Mock(status_code=200)
        sender = StatsSender()

        self.assertEqual(
            sender.send_data_to_url(
                url=sender.build_collector_url("COLLECTOR_ACTION_LOGS_URL"),
                data={}),
            requests_post.return_value
        )
        requests_post.assert_called_once_with(
            sender.build_collector_url("COLLECTOR_ACTION_LOGS_URL"),
            headers={'content-type': 'application/json',
                     'master-node-uid': None},
            data='{}',
            timeout=settings.COLLECTOR_RESP_TIMEOUT)

    @patch('nailgun.statistics.statsenderd.requests.post')
    @patch('nailgun.statistics.statsenderd.logger.error')
    def test_send_failed_on_connection_error(self, log_error, requests_post):
        except_types = (
            urllib3.exceptions.DecodeError,
            urllib3.exceptions.ProxyError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.TooManyRedirects)

        for except_ in except_types:
            requests_post.side_effect = except_()
            sender = StatsSender()
            self.assertIsNone(
                sender.send_data_to_url(
                    url=sender.build_collector_url(
                        "COLLECTOR_ACTION_LOGS_URL"),
                    data={})
            )
            log_error.assert_called_with(
                "Sending data to collector failed: %s",
                type(except_()).__name__)

    @patch('nailgun.statistics.statsenderd.requests.post')
    @patch('nailgun.statistics.statsenderd.logger.exception')
    def test_send_failed_on_exception(self, log_error, requests_post):
        requests_post.side_effect = Exception("custom")
        sender = StatsSender()
        self.assertIsNone(
            sender.send_data_to_url(
                url=sender.build_collector_url("COLLECTOR_ACTION_LOGS_URL"),
                data={})
        )
        log_error.assert_called_once_with(
            "Sending data to collector failed: %s", "custom")

    def test_skipped_action_logs(self):

        class Response(object):
            status_code = 200

            def json(self):
                return {
                    'status': 'ok',
                    'action_logs': [{'external_id': 1, 'status': 'skipped'}]}

        sender = StatsSender()
        commit = 'nailgun.db.sqlalchemy.DeadlockDetectingSession.commit'
        with patch.object(sender, 'send_data_to_url',
                          return_value=Response()):
            with patch.object(sender, 'is_status_acceptable',
                              return_value=True):
                with patch(commit) as mocked_commit:
                    sender.send_log_serialized([{'external_id': 1}], [1])
                    self.assertEqual(0, mocked_commit.call_count)

    @patch('nailgun.statistics.statsenderd.time.sleep')
    @patch('nailgun.statistics.statsenderd.dithered')
    @patch('nailgun.db.sqlalchemy.fixman.settings.'
           'STATS_ENABLE_CHECK_INTERVAL', 0)
    @patch('nailgun.db.sqlalchemy.fixman.settings.'
           'COLLECTOR_PING_INTERVAL', 1)
    def test_send_stats_once_after_dberror(self, dithered, sleep):
        def fn():
            # try to commit wrong data
            Cluster.create(
                {
                    "id": "500",
                    "release_id": "500"
                }
            )
            self.db.commit()

        ss = StatsSender()

        ss.send_stats_once()
        # one call with STATS_ENABLE_CHECK_INTERVAL was made (all went ok)
        self.assertEqual(sleep.call_count, 1)
        dithered.assert_called_with(0)

        with patch('nailgun.objects.MasterNodeSettings.must_send_stats', fn):
            ss.send_stats_once()
        # one more call with COLLECTOR_PING_INTERVAL value
        self.assertEqual(sleep.call_count, 2)
        dithered.assert_called_with(1)

        ss.send_stats_once()
        # one more call was made (all went ok)
        self.assertEqual(sleep.call_count, 3)

    @patch('nailgun.statistics.statsenderd.StatsSender.send_data_to_url')
    def test_oswl_nothing_to_send(self, send_data_to_url):
        dt = datetime.datetime.utcnow()
        obj_data = {
            'cluster_id': 1,
            'resource_type': consts.OSWL_RESOURCE_TYPES.vm,
            'created_date': dt.date(),
            'updated_time': dt.time(),
            'resource_checksum': ""
        }
        obj = OpenStackWorkloadStats.create(obj_data)
        self.assertEqual(
            OpenStackWorkloadStats.get_last_by(
                1, consts.OSWL_RESOURCE_TYPES.vm),
            obj
        )

        StatsSender().send_oswl_info()
        # Nothing to send as it doesn't send today's records. Today's are not
        # sent as they are not complete and can be updated during the day.
        self.assertEqual(send_data_to_url.call_count, 0)

    @patch('nailgun.db.sqlalchemy.fixman.settings.OSWL_COLLECT_PERIOD', 0)
    @patch('nailgun.statistics.statsenderd.StatsSender.send_data_to_url')
    def test_oswl_send_todays_record(self, send_data_to_url):
        dt = datetime.datetime.utcnow()
        obj_data = {
            'cluster_id': 1,
            'resource_type': consts.OSWL_RESOURCE_TYPES.vm,
            'created_date': dt.date(),
            'updated_time': dt.time(),
            'resource_checksum': ""
        }
        obj = OpenStackWorkloadStats.create(obj_data)
        self.assertEqual(
            OpenStackWorkloadStats.get_last_by(
                1, consts.OSWL_RESOURCE_TYPES.vm),
            obj
        )

        StatsSender().send_oswl_info()
        self.assertEqual(send_data_to_url.call_count, 1)

    def check_oswl_data_send_result(self, send_data_to_url, status, is_sent):
        # make yesterdays record (today's will not be sent)
        dt = datetime.datetime.utcnow() - datetime.timedelta(days=1)
        obj_data = {
            'cluster_id': 1,
            'resource_type': consts.OSWL_RESOURCE_TYPES.vm,
            'created_date': dt.date(),
            'updated_time': dt.time(),
            'resource_checksum': ""
        }
        obj = OpenStackWorkloadStats.create(obj_data)
        self.assertEqual(
            OpenStackWorkloadStats.get_last_by(
                1, consts.OSWL_RESOURCE_TYPES.vm),
            obj
        )
        rec_id = obj.id
        self.assertEqual(obj.is_sent, False)

        # emulate the answer from requests.post()
        class response(object):

            status_code = 200

            data = {
                "status": "ok",
                "text": "ok",
                "oswl_stats": [{
                    "master_node_uid": "",
                    "id": rec_id,
                    "status": status
                }]
            }

            def __getitem__(self, key):
                return self.data[key]

            @classmethod
            def json(cls):
                return cls.data

        send_data_to_url.return_value = response

        sender = StatsSender()
        sender.send_oswl_info()

        obj_data_sent = {'oswl_stats': [{
            'id': rec_id,
            'cluster_id': 1,
            'created_date': dt.date().isoformat(),
            'updated_time': dt.time().isoformat(),
            'resource_type': 'vm',
            'resource_checksum': '',
            'master_node_uid': None,
            'resource_data': None,
            'version_info': {}
        }]}
        send_data_to_url.assert_called_once_with(
            url=sender.build_collector_url("COLLECTOR_OSWL_INFO_URL"),
            data=obj_data_sent)

        obj = OpenStackWorkloadStats.get_last_by(
            1, consts.OSWL_RESOURCE_TYPES.vm)
        self.assertEqual(obj.is_sent, is_sent)
        OpenStackWorkloadStats.delete(obj)
        send_data_to_url.reset_mock()

    @patch('nailgun.statistics.statsenderd.StatsSender.send_data_to_url')
    def test_oswl_data_send_results(self, send_data_to_url):
        status_vs_sent = {
            "added": True,
            "updated": True,
            "failed": False
        }
        for status, is_sent in status_vs_sent.iteritems():
            self.check_oswl_data_send_result(send_data_to_url, status, is_sent)

    @patch('nailgun.statistics.statsenderd.requests.post')
    def test_master_node_in_headers(self, requests_post):
        requests_post.return_value = Mock(status_code=200)
        sender = StatsSender()
        url = ''
        data = {}
        master_node_uid = 'xxx'
        MasterNodeSettings.create({'master_node_uid': master_node_uid})

        sender.send_data_to_url(url=url, data={})
        requests_post.assert_called_once_with(
            url,
            headers={'content-type': 'application/json',
                     'master-node-uid': master_node_uid},
            data=json.dumps(data),
            timeout=settings.COLLECTOR_RESP_TIMEOUT)
