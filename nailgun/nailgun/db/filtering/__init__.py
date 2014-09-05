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

import operator

from sqlalchemy import and_

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.errors import errors


class BaseFilter(object):
    """DB objects base filter

    :param mapping_rules_idx dict of BaseFilter.MappingRule: descriptions
    indexed by API parameter name
    :param query sqlalchemy.orm.Query: filtering query
    """

    MAX_PAGE_SIZE = 1000

    def get_mapping_rules(self):
        """Should be implemented in the inherited classes.

        Returns mapping_rules list of BaseFilter.MappingRule: descriptions
        of mapping rules of API params to DB params by SQL operators. To
        be defined in the inherited class

        :return list BaseFilter.MappingRule:
        """
        raise NotImplementedError

    def get_model(self):
        """Should be implemented in the inherited classes.

        Returns DB model for filtering
        :return nailgun.db.sqlalchemy.models.Base:
        """
        raise NotImplementedError

    def __init__(self, filtering, paging=None, ordering=None):
        self.query = db().query(self.get_model())
        self.mapping_rules_idx = self._make_mapping_rules_idx()
        self._filtering = filtering
        self._add_filtering(filtering)
        self._add_ordering(ordering)
        self._add_paging(paging)

    def _make_mapping_rules_idx(self):
        return dict([(r.api_param, r) for r in self.get_mapping_rules()])

    def _add_filtering(self, filtering):
        mapped_keys = filter(lambda x: x in self.mapping_rules_idx, filtering)
        conditions = []
        for k in mapped_keys:
            value = filtering[k]
            mapping_rule = self.mapping_rules_idx[k]
            condition = mapping_rule.get_mapping(self.get_model(), value)
            conditions.append(condition)
        self.query = self.query.filter(and_(*conditions))

    def _add_ordering(self, ordering):
        """Adds order by clause into SQLAlchemy query

        :param ordering: tuple of model fields names or single name
        for ORDER BY criterion. If name starts with '-'
        desc ordering applies, in other case asc.
        """

        if ordering is None:
            return
        if isinstance(ordering, (str, unicode)):
            ordering = [ordering]
        desc_getter = operator.attrgetter('desc')
        asc_getter = operator.attrgetter('asc')
        clauses = []
        for name in ordering:
            field = getattr(self.get_model(), name.lstrip('-'))
            if name.startswith('-'):
                ord_func = desc_getter(field)
            else:
                ord_func = asc_getter(field)
            clauses.append(ord_func())
        self.query = self.query.order_by(*clauses)

    def _add_paging(self, paging):
        if paging is None:
            return
        limit = min(self.MAX_PAGE_SIZE, paging.get('limit', self.MAX_PAGE_SIZE))
        offset = paging.get('offset', 0)
        self.query = self.query.limit(limit)
        self.query = self.query.offset(offset)

    def _handle_lockmode(self, for_update):
        if for_update:
            return self.query.with_lockmode('update')
        else:
            return self.query

    def get_objs(self, for_update=False):
        return self._handle_lockmode(for_update).all()

    def get_objs_count(self):
        return self.query.count()

    def get_one_obj(self, for_update=False):
        objs = self._handle_lockmode(for_update).all()
        if len(objs) > 1:
            raise errors.FoundMoreThanOne(
                "Found more than one {0} by parameters: {1}".format(
                    self.get_model().__tablename__,
                    self._filtering
                )
            )
        elif len(objs) == 0:
            raise errors.ObjectNotFound(
                "Object from {0} is not found by parameters: {1}".format(
                    self.get_model().__tablename__,
                    self._filtering
                )
            )
        else:
            return objs[0]


class MappingRule(object):
    """Rule of mapping API to DB model parameters
    """

    def __init__(self, api_param, model_param, sql_operator):
        self.api_param = api_param
        self.model_attr_getter = operator.attrgetter(model_param)
        self.sql_operator_getter = operator.attrgetter(sql_operator)

    def get_mapping(self, model, value):
        model_attr = self.model_attr_getter(model)
        sql_operator = self.sql_operator_getter(model_attr)
        return sql_operator(value)


class InClusterFilter(BaseFilter):

    def __init__(self, cluster_id, filtering, paging=None, ordering=None):
        self.cluster_id = cluster_id
        new_filtering = dict(cluster_id=self.cluster_id, **filtering)
        super(InClusterFilter, self).__init__(
            new_filtering,
            paging=paging,
            ordering=ordering
        )

    def _make_mapping_rules_idx(self):
        rules_idx = super(InClusterFilter, self)._make_mapping_rules_idx()
        rules_idx['cluster_id'] = MappingRule('cluster_id', 'cluster_id', '__eq__')
        return rules_idx


class TaskFilter(InClusterFilter):

    def get_model(self):
        return models.Task

    def get_mapping_rules(self):
        return [
            MappingRule('id', 'id', '__eq__'),
            MappingRule('name', 'name', '__eq__'),
            MappingRule('names', 'name', 'in_'),
            MappingRule('status', 'status', '__eq__')
        ]
