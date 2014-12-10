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

from collections import defaultdict
import functools
from nose import SkipTest
import os.path
import shutil
import tarfile
import time
from timeit import Timer
from webtest import app

from nailgun.app import build_app
from nailgun.db import db
from nailgun.db import flush
from nailgun.db import syncdb
from nailgun.openstack.common import jsonutils
from nailgun.settings import settings
from nailgun.test.base import BaseTestCase
from nailgun.test.base import EnvironmentManager
from nailgun.test.base import reverse
from nailgun.test.base import test_db_driver
from nailgun.test.performance.profiler import ProfilerMiddleware


class BaseLoadTestCase(BaseTestCase):
    """All load test are long and test suits should be run only in purpose.
    """

    # Number of nodes will be added during the test
    NODES_NUM = 100
    # Maximal allowed execution time of tested handler call
    MAX_EXEC_TIME = 8
    # Maximal allowed slowest calls from TestCase
    TOP_SLOWEST = 10
    # Values needed for creating list of the slowest calls
    slowest_calls = defaultdict(list)

    @classmethod
    def setUpClass(cls):
        if not settings.PERFORMANCE_PROFILING_TESTS:
            raise SkipTest("PERFORMANCE_PROFILING_TESTS in settings.yaml"
                           "is not set")
        if os.path.exists(settings.LOAD_TESTS_PATHS['load_tests_base']):
            shutil.rmtree(settings.LOAD_TESTS_PATHS['load_tests_base'])
        os.makedirs(settings.LOAD_TESTS_PATHS['load_tests_base'])
        cls.app = app.TestApp(build_app(db_driver=test_db_driver).
                              wsgifunc(ProfilerMiddleware))
        syncdb()

    @classmethod
    def tearDownClass(cls):
        """Packs all the files from the profiling.
        """
        if not os.path.exists(settings.LOAD_TESTS_PATHS['load_tests_results']):
            os.makedirs(settings.LOAD_TESTS_PATHS['load_tests_results'])
        if os.path.exists(settings.LOAD_TESTS_PATHS['load_tests_base']):
            # Write list of the slowest calls
            file_path = (settings.LOAD_TESTS_PATHS['load_tests_base'] +
                         'slowest_calls.txt')
            with file(file_path, 'w') as file_o:
                exec_times = sorted(cls.slowest_calls.keys(), reverse=True)
                for exec_time in exec_times:
                    line = '\t'.join([str(exec_time),
                                      '|'.join(cls.slowest_calls[exec_time]),
                                      '\n'])
                    file_o.write(line)

            test_result_name = os.path.join(
                settings.LOAD_TESTS_PATHS['load_tests_results'],
                '{name:s}_{timestamp}.tar.gz'.format(name=cls.__name__,
                                                     timestamp=time.time()))
            tar = tarfile.open(test_result_name, "w:gz")
            tar.add(settings.LOAD_TESTS_PATHS['load_tests_base'])
            tar.close()
            shutil.rmtree(settings.LOAD_TESTS_PATHS['load_tests_base'])

    def setUp(self):
        super(BaseLoadTestCase, self).setUp()
        self.start_time = time.time()

    def tearDown(self):
        """Copy all files from profiling from last test to separate folder.
        Folder name starts from execution time of the test, it will help to
        find data from tests that test bottlenecks
        """
        self.stop_time = time.time()
        exec_time = self.stop_time - self.start_time
        test_path = os.path.join(
            settings.LOAD_TESTS_PATHS['load_tests_base'],
            '{exec_time}_{test_name}'.format(
                exec_time=exec_time,
                test_name=self.__str__().split()[0]))
        shutil.copytree(settings.LOAD_TESTS_PATHS['last_performance_test'],
                        test_path)
        shutil.rmtree(settings.LOAD_TESTS_PATHS['last_performance_test'])

    def check_time_exec(self, func, max_exec_time=None):
        max_exec_time = max_exec_time or self.MAX_EXEC_TIME
        exec_time = Timer(func).timeit(number=1)

        # Checking whether the call should be to the slowest one
        to_add = len(self.slowest_calls) < self.TOP_SLOWEST
        fastest = (sorted(self.slowest_calls.keys())[0]
                   if len(self.slowest_calls) else None)
        if not to_add:
            if fastest < exec_time:
                del self.slowest_calls[fastest]
                to_add = True

        if to_add:
            name = ':'.join([self.__str__(), str(func.args[0])])
            self.slowest_calls[exec_time].append(name)

        self.assertGreater(
            max_exec_time,
            exec_time,
            "Execution time: {0} is greater, than expected: {1}".format(
                exec_time, max_exec_time
            )
        )

    def get_handler(self, handler_name, handler_kwargs={}):
        resp = self.app.get(
            reverse(handler_name, kwargs=handler_kwargs),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        return resp

    def put_handler(self, handler_name, data, handler_kwargs={}):
        resp = self.app.put(
            reverse(handler_name, kwargs=handler_kwargs),
            jsonutils.dumps(data),
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

    def delete_handler(self, handler_name, handler_kwargs={}):
        resp = self.app.delete(
            reverse(handler_name, kwargs=handler_kwargs),
            headers=self.default_headers
        )
        self.assertIn(resp.status_code, (200, 202, 204))
        return resp

    def provision(self, cluster_id, nodes_ids):
        url = reverse(
            'ProvisionSelectedNodes',
            kwargs={'cluster_id': cluster_id}) + \
            '?nodes={0}'.format(','.join(nodes_ids))
        func = functools.partial(self.app.put,
                                 url,
                                 '',
                                 headers=self.default_headers,
                                 expect_errors=True)
        self.check_time_exec(func, 90)

    def deployment(self, cluster_id, nodes_ids):
        url = reverse(
            'DeploySelectedNodes',
            kwargs={'cluster_id': cluster_id}) + \
            '?nodes={0}'.format(','.join(nodes_ids))
        func = functools.partial(self.app.put,
                                 url,
                                 '',
                                 headers=self.default_headers,
                                 expect_errors=True)
        self.check_time_exec(func, 90)


class BaseUnitLoadTestCase(BaseLoadTestCase):

    @classmethod
    def setUpClass(cls):
        super(BaseUnitLoadTestCase, cls).setUpClass()
        cls.app = app.TestApp(
            build_app(db_driver=test_db_driver).wsgifunc(ProfilerMiddleware)
        )
        syncdb()
        cls.db = db
        flush()
        cls.env = EnvironmentManager(app=cls.app, session=cls.db)
        cls.env.upload_fixtures(cls.fixtures)
        cls.cluster = cls.env.create_cluster(api=False)

    @classmethod
    def tearDownClass(cls):
        super(BaseUnitLoadTestCase, cls).tearDownClass()
        cls.db.remove()

    def setUp(self):
        self.start_time = time.time()


class BaseIntegrationLoadTestCase(BaseLoadTestCase):
    # max execution time of whole test
    MAX_TOTAL_EXEC_TIME = 230

    def setUp(self):
        super(BaseIntegrationLoadTestCase, self).setUp()
        self.total_time = self.MAX_TOTAL_EXEC_TIME

    def tearDown(self):
        super(BaseIntegrationLoadTestCase, self).tearDown()
        exec_time = self.stop_time - self.start_time
        self.assertTrue(exec_time <= self.total_time,
                        "Execution time: {exec_time} is greater, "
                        "than expected: {max_exec_time}".format(
                            exec_time=exec_time,
                            max_exec_time=self.total_time))
        self.db.remove()
