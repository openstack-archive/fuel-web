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

import heapq

from timeit import Timer

from nailgun.openstack.common import jsonutils
from nailgun.test.base import BaseTestCase
from nailgun.test.base import reverse


class BaseLoadTestCase(BaseTestCase):

    # Number of nodes will be added during the test
    NODES_NUM = 100
    # Maximal allowed execution time of tested handler call
    MAX_EXEC_TIME = 0.3
    # Maximal allowed execution time degradation of tested handler call
    DEGRADATION_RATE = 2.0

    def growing_nodes_executor(self, func, max_exec_time=MAX_EXEC_TIME,
                               max_nodes_num=NODES_NUM, **node_kwargs):
        times = []
        for _ in xrange(max_nodes_num):
            self.env.create_node(**node_kwargs)
            exec_time = Timer(func).timeit(number=1)
            times.append(exec_time)
            self.assertGreater(
                max_exec_time,
                exec_time,
                "Execution time: {0} is greater, than expected: {1}".format(
                    exec_time, max_exec_time
                )
            )
        return times

    def check_degradation(self, times, degradation_rate=DEGRADATION_RATE,
                          expected_count=NODES_NUM):
        self.assertEquals(expected_count, len(times))
        if degradation_rate is not None:
            # Throwing out the calculation extremal low and high values
            smallest = heapq.nsmallest(3, times)
            largest = heapq.nlargest(3, times)
            act_rate = largest[-1] / smallest[-1]
            self.assertGreater(
                degradation_rate,
                act_rate,
                "Degradation of speed is greater, than expected. "
                "Expected: {0}, actual: {1}".format(degradation_rate, act_rate)
            )

    def get_handler(self, handler_name, id_value, id_name='obj_id'):
        resp = self.app.get(
            reverse(handler_name, kwargs={id_name: id_value}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        return resp

    def put_handler(self, handler_name, request_params, handler_kwargs={}):
        resp = self.app.put(
            reverse(handler_name, kwargs=handler_kwargs),
            jsonutils.dumps(request_params),
            headers=self.default_headers
        )
        self.assertIn(resp.status_code, (200, 202))
        return resp

    def patch_handler(self, handler_name, request_params, handler_kwargs={}):
        resp = self.app.patch(
            reverse(handler_name, kwargs=handler_kwargs),
            params=jsonutils.dumps(request_params),
            headers=self.default_headers
        )
        self.assertIn(resp.status_code, (200, 202))
        return resp

    def post_handler(self, handler_name, obj_data, handler_kwargs={}):
        resp = self.app.post(
            reverse(handler_name, kwargs=handler_kwargs),
            jsonutils.dumps(obj_data),
            headers=self.default_headers
        )
        self.assertIn(resp.status_code, (200, 201))
        return resp

    def delete_handler(self, handler_name, obj_id, id_name='obj_id'):
        resp = self.app.delete(
            reverse(handler_name, kwargs={id_name: obj_id}),
            headers=self.default_headers
        )
        self.assertIn(resp.status_code, (200, 202, 204))
        return resp
