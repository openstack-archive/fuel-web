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

from mock import patch
import tempfile

from nailgun.monitor import monitord
from nailgun import objects
from nailgun.settings import settings
from nailgun.test.base import BaseIntegrationTest


class MonitordTest(BaseIntegrationTest):
    def test_disk_space_monitor(self):
        temp_file = tempfile.NamedTemporaryFile()

        with patch.dict('nailgun.settings.settings.MONITORD', {
            'free_disk_error': 10,
            'states_file': temp_file.name,
        }):
            # No data at first
            state = monitord.read_state('disk_space')
            self.assertIsNone(state['alert_date'])
            self.assertEqual(len(state['message']), 0)
            notification_count = objects.NotificationCollection.count()

            # Make sure we get the disk space warning
            settings.MONITORD['free_disk_error'] = 10000  # 10 TB
            monitord.monitor_fuel_master()

            # Make sure we get warning about free disk space
            state = monitord.read_state('disk_space')
            self.assertIsNotNone(state['alert_date'])
            self.assertGreater(len(state['message']), 0)
            # Notification was created
            self.assertEqual(
                objects.NotificationCollection.count(),
                notification_count + 1
            )
            # Get last added notification and make sure it's correct
            noti = objects.NotificationCollection.all().order_by('-id')[0]

            self.assertEqual(noti.message, state['message'])

            # Make sure that running monitor once again doesn't create
            # new notification
            monitord.monitor_fuel_master()
            self.assertEqual(
                objects.NotificationCollection.count(),
                notification_count + 1
            )

            # Now simulate free disk space getting to OK state
            settings.MONITORD['free_disk_error'] = 0  # 0 GB
            monitord.monitor_fuel_master()

            state = monitord.read_state('disk_space')
            self.assertIsNone(state['alert_date'])
            self.assertEqual(len(state['message']), 0)
            # Notification was created
            self.assertEqual(
                objects.NotificationCollection.count(),
                notification_count + 2
            )
            noti = objects.NotificationCollection.all().order_by('-id')[0]
            self.assertEqual(noti.topic, 'done')
