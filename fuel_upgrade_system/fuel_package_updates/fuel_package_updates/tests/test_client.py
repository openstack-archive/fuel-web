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
import json

import httpretty
import unittest2

from fuel_package_updates import fuel_package_updates as fpu
from fuel_package_updates.tests import base


class TestFuelWebClient(unittest2.TestCase):

    # TODO(prmtl): after moving whole script to requests, use requests_mock
    @httpretty.activate
    def test_get_available_releases(self):
        ip = '127.0.0.1'
        fwc = fpu.FuelWebClient(ip)
        release = base.make_release()
        body = json.dumps([
            release,
        ])
        httpretty.register_uri(
            httpretty.GET,
            'http://{ip}:8000/api/releases/'.format(ip=ip),
            body=body,
        )

        releases = list(fwc.get_available_releases())

        self.assertEqual(len(releases), 1)
        self.assertEqual(releases[0], release)
