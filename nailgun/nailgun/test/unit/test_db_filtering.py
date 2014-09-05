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

import mock

from nailgun.db.filtering import BaseFilter
from nailgun.db.filtering import MappingRule
from nailgun.db.sqlalchemy import db
from nailgun.db.sqlalchemy import models
from nailgun.errors import errors
from nailgun.test.base import BaseTestCase


class TestDbFiltering(BaseTestCase):

    @classmethod
    def setUpClass(cls):
        cls.patcher = mock.patch.object(BaseFilter, 'get_model', return_value=models.Cluster)
        cls.patcher.start()
        super(TestDbFiltering, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(TestDbFiltering, cls).tearDownClass()
        cls.patcher.stop()

    def test_get_objs_filtering(self):
        name_one = 'one'
        name_two = 'two'
        self.env.create_cluster(name=name_one)
        self.env.create_cluster(name=name_two)
        self.env.clusters[0]['replaced_deployment_info'] = None
        db().flush()

        mapping_rules = [
            MappingRule('name', 'name', '__eq__'),
            MappingRule('names', 'name', 'in_'),
            MappingRule(
                'replaced_deployment_info',
                'replaced_deployment_info',
                '__eq__'
            )
        ]

        with mock.patch.object(BaseFilter, 'get_mapping_rules', return_value=mapping_rules):

            # checking no filtering
            f = BaseFilter({})
            objs = f.get_objs()
            self.assertEquals(len(self.env.clusters), len(objs))
            self.assertItemsEqual(
                [o.id for o in self.env.clusters],
                [o.id for o in objs]
            )

            # checking filtering by parameter value
            f = BaseFilter({'name': name_one})
            objs = f.get_objs()
            self.assertEquals(1, len(objs))
            self.assertEquals(name_one, objs[0].name)

            # checking filtering by NULL parameter value
            f = BaseFilter({'name': None})
            objs = f.get_objs()
            self.assertEquals(0, len(objs))

            f = BaseFilter({'replaced_deployment_info': None})
            objs = f.get_objs()
            self.assertEquals(1, len(objs))
            self.assertEquals(name_one, objs[0].name)

            # checking filtering by list of values
            f = BaseFilter({'names': [name_two]})
            objs = f.get_objs()
            self.assertEquals(1, len(objs))
            self.assertEquals(name_two, objs[0].name)

            # checking unknown mapping
            f = BaseFilter({'fake': 'fake_value'})
            objs = f.get_objs()
            self.assertEquals(len(self.env.clusters), len(objs))
            self.assertItemsEqual(
                [o.id for o in self.env.clusters],
                [o.id for o in objs]
            )

    def test_get_obj_filtering(self):
        name_one = 'one'
        name_two = 'two'
        self.env.create_cluster(name=name_one)
        self.env.create_cluster(name=name_two)
        mapping_rules = [
            MappingRule('name', 'name', '__eq__'),
            MappingRule('name_like', 'name', 'like'),
        ]

        with mock.patch.object(BaseFilter, 'get_mapping_rules', return_value=mapping_rules):

            f = BaseFilter({})
            self.assertRaises(errors.FoundMoreThanOne, f.get_one_obj)

            f = BaseFilter({'name': 'not_existed'})
            self.assertRaises(errors.ObjectNotFound, f.get_one_obj)
            f.get_one_obj()

            f = BaseFilter({'name': name_one})
            obj = f.get_one_obj()
            self.assertEquals(name_one, obj.name)

    def test_objs_count(self):
        name_one = 'one'
        name_two = 'two'
        self.env.create_cluster(name=name_one)
        self.env.create_cluster(name=name_two)
        mapping_rules = [
            MappingRule('name', 'name', '__eq__'),
        ]

        with mock.patch.object(BaseFilter, 'get_mapping_rules', return_value=mapping_rules):

            f = BaseFilter({})
            self.assertEquals(len(self.env.clusters), f.get_objs_count())

            f = BaseFilter({'name': name_one})
            self.assertEquals(1, f.get_objs_count())

    def test_handle_lockmode(self):
        with mock.patch.object(BaseFilter, 'get_mapping_rules', return_value=[]):
            f = BaseFilter({})
            query = f._handle_lockmode(True)
            self.assertTrue('FOR UPDATE' in str(query))
            query = f._handle_lockmode(False)
            self.assertFalse('FOR UPDATE' in str(query))

    def test_paging(self):
        self.env.create_cluster()
        self.env.create_cluster()
        with mock.patch.object(BaseFilter, 'get_mapping_rules', return_value=[]):
            f = BaseFilter({})
            total = f.get_objs_count()
            for limit in xrange(total + 1):
                f = BaseFilter({}, paging={'limit': limit})
                self.assertEquals(limit, f.get_objs_count())

            for offset in xrange(total + 1):
                f = BaseFilter({}, paging={'offset': offset})
                self.assertEquals(total - offset, f.get_objs_count())

    def test_ordering(self):
        for _ in xrange(10):
            self.env.create_cluster()
        with mock.patch.object(BaseFilter, 'get_mapping_rules', return_value=[]):

            f = BaseFilter({}, ordering='id')
            objs = f.get_objs()
            self.assertEquals(
                sorted(objs, key=lambda x: x.id),
                objs
            )

            f = BaseFilter({}, ordering=['-id'])
            objs = f.get_objs()
            self.assertEquals(
                sorted(objs, key=lambda x: x.id, reverse=True),
                objs
            )

            f = BaseFilter({}, ordering=['-id', 'name'])
            objs = f.get_objs()
            self.assertEquals(
                sorted(
                    sorted(objs, key=lambda x: x.name),
                    key=lambda x: x.id,
                    reverse=True
                ),
                objs
            )
