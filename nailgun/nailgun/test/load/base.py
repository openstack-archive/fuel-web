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

import os.path
import shutil
import tarfile
import time
import unittest2 as unittest

from timeit import Timer
from webtest import app

from nailgun.app import build_app
from nailgun import consts
from nailgun.db import db
from nailgun.db import flush
from nailgun.db import syncdb
from nailgun.openstack.common import jsonutils
from nailgun.test.base import BaseTestCase
from nailgun.test.base import Environment
from nailgun.test.base import reverse
from nailgun.test.base import test_db_driver


@unittest.skipUnless(os.environ.get('LoadTest'),
                     "Enviroment variable LoadTest is not set")
class BaseLoadTestCase(BaseTestCase):
    """All load test are long and test suits should be run only in purpose.
    """

    # Number of nodes will be added during the test
    NODES_NUM = 100
    # Maximal allowed execution time of tested handler call
    MAX_EXEC_TIME = 8

    @classmethod
    def setUpClass(cls):
        if os.path.exists(consts.LOAD_TESTS_PATHS.load_tests_base):
            shutil.rmtree(consts.LOAD_TESTS_PATHS.load_tests_base)
        os.makedirs(consts.LOAD_TESTS_PATHS.load_tests_base)
        super(BaseLoadTestCase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        """Packs all the files from the profiling.
        """
        if not os.path.exists(consts.LOAD_TESTS_PATHS.load_tests_results):
            os.makedirs(consts.LOAD_TESTS_PATHS.load_tests_results)
        if os.path.exists(consts.LOAD_TESTS_PATHS.load_tests_base):
            test_result_name = os.path.join(
                consts.LOAD_TESTS_PATHS.load_tests_results,
                '%s_%d.tar.gz' % (cls.__name__, time.time()))
            tar = tarfile.open(test_result_name, "w:gz")
            tar.add(consts.LOAD_TESTS_PATHS.load_tests_base)
            tar.close()
            shutil.rmtree(consts.LOAD_TESTS_PATHS.load_tests_base)

    def setUp(self):
        super(BaseLoadTestCase, self).setUp()
        self.start_time = time.time()

    def tearDown(self):
        """Copy all files from profiling from last test to separate folder.
        Folder name starts from execution time of the test, it will help to
        find data from tests that test bottlenecks
        """
        self.stop_time = time.time()
        exec_time = self.start_time - self.stop_time
        test_path = os.path.join(
            consts.LOAD_TESTS_PATHS.load_tests_base,
            '{0}{1}'.format(exec_time, self.__str__().split()[0]))
        shutil.copytree(consts.LOAD_TESTS_PATHS.last_load_test, test_path)
        shutil.rmtree(consts.LOAD_TESTS_PATHS.last_load_test)

    def check_time_exec(self, func, max_exec_time=None):
        max_exec_time = max_exec_time or self.MAX_EXEC_TIME
        exec_time = Timer(func).timeit(number=1)
        self.assertGreater(
            max_exec_time,
            exec_time,
            "Execution time: {0} is greater, than expected: {1}".format(
                exec_time, max_exec_time
            )
        )

    def get_handler(self, handler_name, id_value, id_name='obj_id'):
        resp = self.app.get(
            reverse(handler_name, kwargs={id_name: id_value}),
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

    def provision(self, cluster_id, nodes_ids):
        url = reverse(
            'ProvisionSelectedNodes',
            kwargs={'cluster_id': cluster_id}) + \
            '?nodes={0}'.format(','.join(nodes_ids))
        self.app.put(
            url, '', headers=self.default_headers, expect_errors=True)

    def deployment(self, cluster_id, nodes_ids):
        url = reverse(
            'DeploySelectedNodes',
            kwargs={'cluster_id': cluster_id}) + \
            '?nodes={0}'.format(','.join(nodes_ids))
        self.app.put(
            url, '', headers=self.default_headers, expect_errors=True)

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


class BaseUnitLoadTestCase(BaseLoadTestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = app.TestApp(build_app(db_driver=test_db_driver).
                              wsgifunc())
        syncdb()
        cls.db = db
        flush()
        cls.env = Environment(app=cls.app, session=cls.db)
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
    MAX_TOTAL_EXEC_TIME = 200

    def setUp(self):
        super(BaseIntegrationLoadTestCase, self).setUp()
        self.total_time = self.MAX_TOTAL_EXEC_TIME

    def tearDown(self):
        super(BaseIntegrationLoadTestCase, self).tearDown()
        self.assertTrue(self.stop_time - self.start_time <= self.total_time)
