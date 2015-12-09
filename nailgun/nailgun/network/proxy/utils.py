from nailgun.db import db

from sqlalchemy import and_
from sqlalchemy import not_
from sqlalchemy import or_


class Query(object):

    def __init__(self, model, data):
        self.model = model
        self.filters = self._create_filters(data)
        self.limit = None
        self.offset = 0
        self.order_by = None
        self.group_by = None
        self.options = data.get('options', {})

    def _create_filters(self, data):
        output = []
        for f in data.get('filters', []):
            output.append(Filter.from_dict(f))

        return output

    def _create_sa_filter(self, f, relation=None):
        field = getattr(self.model, relation or f.name)
        if f.op == 'eq':
            func = lambda field, value: field == value
        if f.op == 'gt':
            func = lambda field, value: field > value
        if f.op == 'gte':
            func = lambda field, value: field >= value
        if f.op == 'lt':
            func = lambda field, value: field < value
        if f.op == 'lte':
            func = lambda field, value: field <= value
        if f.op == 'in':
            func = lambda field, values: field.in_(values)
        if f.op == 'is':
            func = lambda field, value: field.is_(value)
        if f.op == 'isnot':
            func = lambda field, value: field.isnot(value)

        if relation:
            model = field.property.mapper.class_
            field = getattr(model, f.name)

        return func(field, f.val)

    def _create_order_by(self, query, order_by):
        for field_name in order_by:
            if field_name.startswith('-'):
                field_name = field_name.lstrip('-')
                ordering = 'desc'
            else:
                ordering = 'asc'
            field = getattr(self.model, field_name)
            o_func = getattr(field, ordering)
            query = query.order_by(o_func())
        return query

    def render(self):
        q = db().query(self.model)
        for f in self.filters:
            if isinstance(f, BoolFilter):
                if f.type == 'or':
                    q = q.filter(or_(
                        self._create_sa_filter(fil) for fil in f.filters))
                elif f.type == 'and':
                    q = q.filter(and_(
                        self._create_sa_filter(fil) for fil in f.filters))
                elif f.type == 'not':
                    q = q.filter(not_(self._create_sa_filter(f.filters[0])))
            else:
                relation = None
                if '__' in f.name:
                    relation, field_name = f.name.split('__')
                    f.name = field_name
                    rel_field = getattr(self.model, relation)
                    rel_model = rel_field.property.mapper.class_
                    q = q.join(rel_model)

                op_func = self._create_sa_filter(f, relation)
                q = q.filter(op_func)

        if self.options.get('distinct'):
            q = q.distinct(self.options['distinct'])

        if self.options.get('order_by'):
            q = self._create_order_by(q, self.options['order_by'])
        return q


class Filter(object):

    def __init__(self, name, op, val=None, field=None):
        self.name = name
        self.op = op
        self.val = val
        self.field = field

    def __repr__(self):
        return '<Filter {0}, {1}, {2}>'.format(self.name, self.op, self.val)

    @staticmethod
    def from_dict(data):
        if 'or' in data:
            return BoolFilter('or', *(Filter.from_dict(x) for x in data['or']))
        if 'and' in data:
            return BoolFilter(
                'and', *(Filter.from_dict(x) for x in data['and']))
        if 'not' in data:
            return BoolFilter('not', Filter.from_dict(data['not']))

        name = data.get('name')
        op = data.get('op')
        val = data.get('val')
        field = data.get('field')

        return Filter(name, op, val, field)


class BoolFilter(object):

    def __init__(self, type, *args):
        self.filters = args
        self.type = type

    def __repr__(self):
        return '<{0}: [{1}]>'.format(
            self.__class__.__name__, ', '.join(repr(f) for f in self.filters))
