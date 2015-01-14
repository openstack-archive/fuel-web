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

from nailgun.test.performance.base import BaseUnitLoadTestCase
from nailgun.test.performance.base import evaluate_unit_performance


class NotificationOperationsLoadTest(BaseUnitLoadTestCase):

    NOTIFICATIONS_NUM = 1000

    @classmethod
    def setUpClass(cls):
        super(NotificationOperationsLoadTest, cls).setUpClass()
        for _ in six.moves.range(0, cls.NOTIFICATIONS_NUM):
            cls.env.create_notification()

    @evaluate_unit_performance
    def test_notifications_retrieval(self):
        func = functools.partial(
            self.get_handler,
            'NotificationCollectionHandler',
        )

        self.check_time_exec(func)

    @evaluate_unit_performance
    def test_notifications_creation(self):
        n = self.env.create_notification()
        data = [dict(dict(n), id=i)
                for i in six.moves.range(1, self.NOTIFICATIONS_NUM + 1)]

        func = functools.partial(
            self.put_handler,
            'NotificationCollectionHandler',
            data
        )

        self.check_time_exec(func, 20)
