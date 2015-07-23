# -*- coding: utf-8 -*-
#
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

import csv
from datetime import datetime
import os

from oslo_serialization import jsonutils
import pytz
import six

from nailgun.settings import settings


class PerformanceDataCsvCreator(object):
    NEW_REPORT_FILE_NAME = 'nailgun_perf_test_report.csv'
    OLD_REPORT_FILE_NAME = 'nailgun_perf_test_report.csv'
    DATE_FIELD_NAME = 'date'
    CURRENT_RUN_DATA_PATH = settings.LOAD_TESTS_PATHS[
        'load_previous_tests_results'
    ]

    def __init__(self):
        self.column_names = [self.DATE_FIELD_NAME]
        self.report_data = []
        self.has_historic_data = os.path.isfile(self.OLD_REPORT_FILE_NAME)

    def read_data(self):
        self._read_historic_data()
        self._read_current_data()

    def save_data(self):
        with open(self.NEW_REPORT_FILE_NAME, 'wb') as report:
            data_writer = csv.DictWriter(report, fieldnames=self.column_names)

            data_writer.writerow(
                dict(six.moves.zip(self.column_names, self.column_names)))
            for row in self.report_data:
                data_writer.writerow(row)

    def _read_historic_data(self):
        if self.has_historic_data:
            with open(self.OLD_REPORT_FILE_NAME, 'rb') as report:
                hist_data_reader = csv.DictReader(report)
                self.column_names += hist_data_reader.fieldnames[1:]

                self.report_data += list(hist_data_reader)

    def _read_current_data(self):
        with open(self.CURRENT_RUN_DATA_PATH) as file:
            data = jsonutils.load(file)

        tests = self._flatten_json_dictionary(data)

        now = datetime.now(tz=pytz.utc)

        current_test_data = dict(date=now.isoformat())

        for key, test in tests:
            if key not in self.column_names:
                self.column_names.append(key)

            current_test_data[key] = sum(
                [t[1]['expect_time'] for t in test.items()]
            )

        self.report_data.append(current_test_data)

    def _flatten_json_dictionary(self, data):
        return [
            item for sublist in [
                sub[1].items() for sub in six.iteritems(data)
            ] for item in sublist
        ]


def save_failed_tests(reports):
    FAILED_TESTS_FILE_NAME = settings.LOAD_TESTS_PATHS[
        'failed_test_file_name'
    ]

    failed_ids = [x.nodeid for x in reports if x.failed]

    with open(FAILED_TESTS_FILE_NAME, 'w') as fail_file:
        fail_file.write("\n".join(failed_ids))
