# -*- coding: utf-8 -*-
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

import functools
import six

from nailgun.test.performance import base


class NotificationOperationsLoadTest(base.BaseUnitLoadTestCase):

    NOTIFICATIONS_NUM = 1000

    @classmethod
    def setUpClass(cls):
        super(NotificationOperationsLoadTest, cls).setUpClass()
        cls.notifications = []
        for _ in six.moves.range(0, cls.NOTIFICATIONS_NUM):
            cls.notifications.append(cls.env.create_notification())

    @base.evaluate_unit_performance
    def test_notifications_retrieval(self):
        func = functools.partial(
            self.get_handler,
            'NotificationCollectionHandler',
        )

        self.check_time_exec(func)

    @base.evaluate_unit_performance
    def test_notifications_creation(self):
        data = [dict(n) for n in self.notifications]

        func = functools.partial(
            self.put_handler,
            'NotificationCollectionHandler',
            data
        )

        self.check_time_exec(func, 20)
