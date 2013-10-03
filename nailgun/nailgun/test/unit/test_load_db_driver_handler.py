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


from sqlalchemy import exc
import unittest

from nailgun.db import db, load_db_driver
from nailgun.api import models
from nailgun.errors import errors, NailgunException
import web


class TestLoadDBDriverHandler(unittest.TestCase):

    def test_session_invalid_request_error(self):
        """Test verifies reason why load_db_driver
        failes with InvalidRequestError
        """

        def handler_sample():
            try:
                db().add(models.Role())
                db().flush()
            except exc.IntegrityError:
                db().commit()

        self.assertRaises(exc.InvalidRequestError, handler_sample)

    def test_session_integrity_error(self):
        """Test verifies reason why load_db_driver
        failes with InvalidRequestError
        """

        def handler_sample():
            try:
                db().add(models.Role())
                db().flush()
            except exc.IntegrityError:
                db().rollback()
                raise

        self.assertRaises(exc.IntegrityError, handler_sample)

    def test_session_state_after_random_error(self):
        """Test verifies that expected error would be raised in case of errors
        happened not during flush
        """

        def handler_sample():
            db().add(models.Role())
            raise errors.DumpError()

        self.assertRaises(NailgunException, load_db_driver, handler_sample)

    def test_session_state_after_random_error_and_flush(self):

        def handler_sample():
            db().add(models.Role())
            db().flush()
            raise errors.DumpError()

        self.assertRaises(exc.IntegrityError, load_db_driver, handler_sample)

    def test_load_db_driver_with_web_error(self):

        def handler_sample():
            db().add(models.Role())
            raise web.HTTPError(400)

        self.assertRaises(web.HTTPError,
                          load_db_driver, handler_sample)

    def tearDown(self):
        db().rollback()
