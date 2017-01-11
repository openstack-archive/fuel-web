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

import pytest

from nailgun.test.performance import perf_data_gatherer


PERFORMANCE_NAME = 'performance'


reports = []


def pytest_sessionfinish(session, exitstatus):
    if PERFORMANCE_NAME == pytest.config.known_args_namespace.markexpr:
        generator = perf_data_gatherer.PerformanceDataCsvCreator()
        generator.read_data()
        generator.save_data()

        perf_data_gatherer.save_failed_tests(reports)


def pytest_report_teststatus(report):
    if report.when == 'call':
        reports.append(report)
