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
import os.path
import shutil
import six
import tarfile
import time
from timeit import Timer
from webtest import app

from oslo_serialization import jsonutils

from nailgun.app import build_app
from nailgun.db import db
from nailgun.db import flush
from nailgun.db import syncdb
from nailgun.settings import settings
from nailgun.test.base import BaseTestCase
from nailgun.test.base import EnvironmentManager
from nailgun.test.base import test_db_driver
from nailgun.test.performance.profiler import ProfilerMiddleware
from nailgun.utils import reverse

import pytest


@pytest.mark.performance
class BaseLoadTestCase(BaseTestCase):
    """All load test are long and test suits should be run only in purpose."""

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
        if os.path.exists(settings.LOAD_TESTS_PATHS['load_tests_base']):
            shutil.rmtree(settings.LOAD_TESTS_PATHS['load_tests_base'])
        os.makedirs(settings.LOAD_TESTS_PATHS['load_tests_base'])
        cls.app = app.TestApp(build_app(db_driver=test_db_driver).
                              wsgifunc(ProfilerMiddleware))
        syncdb()
        cls.tests_results = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list)))
        cls.tests_stats = defaultdict(lambda: defaultdict(dict))

    @classmethod
    def tearDownClass(cls):
        """Packs all the files from the profiling."""
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
                    file_o.write(six.text_type(line))

            test_result_name = os.path.join(
                settings.LOAD_TESTS_PATHS['load_tests_results'],
                '{name:s}_{timestamp}.tar.gz'.format(name=cls.__name__,
                                                     timestamp=time.time()))
            tar = tarfile.open(test_result_name, "w:gz")
            tar.add(settings.LOAD_TESTS_PATHS['load_tests_base'])
            tar.close()
            shutil.rmtree(settings.LOAD_TESTS_PATHS['load_tests_base'])
        write_results(str(cls.__name__), cls.tests_stats)

    def setUp(self):
        super(BaseLoadTestCase, self).setUp()
        self.start_time = time.time()
        self.call_number = 1

    def tearDown(self):
        """Copy all files from profiling from last test to separate folder

        Folder name starts from execution time of the test, it will help to
        find data from tests that test bottlenecks
        """
        self.stop_time = time.time()
        exec_time = self.stop_time - self.start_time
        test_path = os.path.join(
            settings.LOAD_TESTS_PATHS['load_tests_base'],
            '{exec_time}_{test_name}'.format(
                exec_time=exec_time,
                test_name=str(self).split()[0]))
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
        test_name = str(self)
        request_name = str(func.args[0])
        name = ':'.join([test_name, request_name])
        if not to_add:
            if fastest < exec_time:
                del self.slowest_calls[fastest]
                to_add = True

        if to_add:
            self.slowest_calls[exec_time].append(name)

        test_results_d = self.tests_results[test_name][str(self.call_number)]
        test_results_d['results'].append(exec_time)
        if self.call_number == 1:
            test_results_d['request_name'] = request_name
            test_results_d['expect_time'] = max_exec_time
        self.call_number += 1

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
        self.call_number = 1


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


def copy_test_results(run_number):
    """Copy test result from separate run to new directory.

    :parameter run_number: run number, used in creating new directory
    """
    path_to_write = os.path.join(
        settings.LOAD_TESTS_PATHS['last_performance_test'],
        'run{0}'.format(run_number))
    shutil.copytree(settings.LOAD_TESTS_PATHS['last_performance_test_run'],
                    path_to_write)
    shutil.rmtree(settings.LOAD_TESTS_PATHS['last_performance_test_run'])


def normalize(N, percentile):
    """Normalize N and remove first and last percentile

    :parameter N:          is a list of values.
    :parameter percentile: a float value from 0.0 to 1.0.

    :return:               the percentile of the values
    """
    if not N:
        return None
    k = (len(N) - 1) * percentile
    floor = int(k)
    return sorted(N)[floor:len(N) - floor - 1]


def read_previous_results():
    """Read results of previous run.

    :return: dictionary of results if exist
    """
    try:
        with open(settings.LOAD_TESTS_PATHS['load_previous_tests_results'],
                  'r') as results_file:
            results = jsonutils.load(results_file)
    except (IOError, ValueError):
        results = {}
    return results


def write_results(test_class_name, results):
    """Write tests results to file defined in settings."""
    prev_results = read_previous_results()
    if test_class_name in prev_results:
        prev_results[test_class_name].update(results)
    else:
        prev_results[test_class_name] = results
    with open(settings.LOAD_TESTS_PATHS['load_previous_tests_results'],
              'w') as results_file:
            results_file.write(
                jsonutils.dumps(prev_results, sort_keys=True, indent=4))


def evaluate_unit_performance(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        # read results of previous correct run
        test = args[0]
        number_of_runs = settings.PERFORMANCE_TESTS_RUN_NUMBER

        # run tests multiple time to get more exact results
        for run in six.moves.range(number_of_runs):
            f(*args, **kwargs)
            copy_test_results(run)
            # reset call number for unittests
            test.call_number = 1

        compare_with_previous = False
        class_name = test.__class__.__name__
        previous_test_results = read_previous_results().get(class_name, {}).\
            get(str(test), {})
        current_rest_results = test.tests_results[str(test)]
        if len(previous_test_results) == len(current_rest_results):
            compare_with_previous = True

        for call_number, results in six.iteritems(
                test.tests_results[str(test)]):
            request_name = results['request_name']

            # normalize results and compute avg
            normalized = normalize(results['results'], 0.025)
            avg_time = sum(normalized) / len(normalized)

            # check if previous results exists
            prev_time = None
            if compare_with_previous:
                if request_name in \
                   previous_test_results[call_number]['request_name']:
                    # we give some % (default 10%) of tolerance for previous
                    # expected time
                    prev_time = (
                        previous_test_results[call_number]['expect_time'] *
                        (1.0 + settings.PERFORMANCE_TESTS_TOLERANCE))
            expect_time = prev_time or results['expect_time']
            test.tests_results[str(test)]
            test.assertTrue(
                avg_time <= expect_time,
                "Average execution time: {exec_time} is greater, "
                "than expected: {max_exec_time}".format(
                    exec_time=avg_time,
                    max_exec_time=expect_time))
            test.tests_stats[str(test)][call_number]['request_name'] =\
                request_name
            test.tests_stats[str(test)][call_number]['expect_time'] =\
                avg_time

    return wrapper
