# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

import datetime
import unittest

import web

from nailgun.api.v1.handlers import load_db_driver
from nailgun.db import db
from nailgun.db.sqlalchemy import models


class TestLoadDbDriverWithSAExceptions(unittest.TestCase):
    def setUp(self):
        web.ctx.headers = []

    def tearDown(self):
        db.rollback()

    def test_sa_not_null_constraint(self):
        def handler():
            node = models.Node(mac=None)
            db.add(node)
            db.flush()

        self.assertRaises(web.HTTPError, load_db_driver, handler)

    def test_sa_unique_constraint(self):
        def handler():
            mac = '60:a4:4c:35:28:95'

            node1 = models.Node(mac=mac, timestamp=datetime.datetime.now())
            db.add(node1)
            db.flush()

            node2 = models.Node(mac=mac, timestamp=datetime.datetime.now())
            db.add(node2)
            db.flush()

        self.assertRaises(web.HTTPError, load_db_driver, handler)

    def test_sa_enum_constraint(self):
        def handler():
            node = models.Node(
                mac='60:a4:4c:35:28:95',
                timestamp=datetime.datetime.now(),
                status='batman'
            )
            db.add(node)
            db.flush()

        self.assertRaises(web.HTTPError, load_db_driver, handler)

    def test_sa_relationship_constraint(self):
        def handler():
            node = models.Node(
                mac='60:a4:4c:35:28:95',
                timestamp=datetime.datetime.now()
            )

            node.attributes = models.IPAddr()
            db.add(node)
            db.flush()

        self.assertRaises(AssertionError, load_db_driver, handler)
