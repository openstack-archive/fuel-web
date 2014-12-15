# -*- coding: utf-8 -*-

#    Copyright 2014 Mirantis, Inc.
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

import re

import six

from nailgun.settings import settings
from nailgun.test import base


class TestSettings(base.BaseTestCase):

    def test_log_format_remote_openstack(self):
        syslog_w_app = (
            '2014-12-12T11:00:30.098105+00:00 info: 2014-12-12 11:00:30.003 '
            '14349 INFO neutron.common.config [-] Logging enabled!')
        syslog = (
            '2014-12-12T10:57:15.437488+00:00 debug: Loading app ec2 from '
            '/etc/nova/api-paste.ini')

        openstack_format = filter(
            lambda log: log['log_format_id'] == 'remote_openstack',
            settings.LOG_FORMATS)[0]

        regexp = re.compile(openstack_format['regexp'])
        syslog_w_app_re = regexp.match(syslog_w_app)
        syslog_re = regexp.match(syslog)

        syslog_result = {
            'text': 'Loading app ec2 from /etc/nova/api-paste.ini',
            'level': 'debug',
            'date': '2014-12-12T10:57:15'}

        syslog_w_app_result = {
            'text': 'neutron.common.config [-] Logging enabled!',
            'level': 'info',
            'date': '2014-12-12T11:00:30'}

        for group, value in six.iteritems(syslog_result):
            self.assertEqual(syslog_re.group(group),
                             syslog_result[group])

        for group, value in six.iteritems(syslog_w_app_result):
            self.assertEqual(syslog_w_app_re.group(group),
                             syslog_w_app_result[group])
