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
        self.query = None

    def _create_filters(self, data):
        """Create Filter objects with provided data.

        :param data: dictionary with filter definitions
        :returns: list of Filter instances
        """
        output = []
        for f in data.get('filters', []):
            output.append(Filter.from_dict(f))

        return output

    def _create_sa_filter(self, f, model=None, relation=None):
        """Creates a SQLAlchemy BinaryExpression.

        A different model can be provided along with relation in order
        to create a filter function on a model that isn't self.model.

        Relation is provided because when a filter is being created for
        a field on a joined table the field name will 'A__B__somefield'.
        In this case A.<field name> will not exist. Instead B should be
        passed as the model and 'somefield' as relation. This will create
        the filter function on B.somefield.

        :param f: Filter object
        :param model: Model
        :param relation: Related field name to use in place of f.name.
        :returns: SQLAlchemy BinaryExpression
        """
        model = model or self.model
        field = getattr(model, relation or f.name)
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
        if f.op == 'ne':
            func = lambda field, value: field != value

        return func(field, f.val)

    def _create_order_by(self, order_by):
        """Add ORDER BY to query.

        This method iterates over a list of field names and adds an
        ORDER BY for each one. If the field name is prefaced with '-'
        it will add DESC.

        :param order_by: list of fields to order results by
        :returns: None
        """
        for field_name in order_by:
            if field_name.startswith('-'):
                field_name = field_name.lstrip('-')
                ordering = 'desc'
            else:
                ordering = 'asc'
            field = getattr(self.model, field_name)
            o_func = getattr(field, ordering)
            self.query = self.query.order_by(o_func())

    def _expand_filter(self, f):
        """Expand BoolFilters into SQLAlchemy expressions.

        This method will recursively expand BoolFilters and join the
        created filter functions with and_() or or_() appropriately.

        :returns: SQLAlchemy BinaryExpression
        """
        if isinstance(f, BoolFilter):
            if f.type == 'or':
                return or_(self._expand_filter(fil) for fil in f.filters)
            if f.type == 'and':
                return and_(self._expand_filter(fil) for fil in f.filters)
        return self._create_sa_filter(f)

    def _expand_relation(self,  filter):
        """Joins intermediate tables required for query.

        If filter.name is model1__model2__fieldname then this method will
        result in the following:

        self.query = self.query.join(
            model1
        ).join(
            model2
        ).filter(
            model2.fieldname == value
        )

        :param filter: Filter instance
        :returns: Tuple containting the related field name and model
        """
        relation = None
        rel_model = self.model
        if '__' in filter.name:
            values = filter.name.split('__')
            # The last item in the list will be the field name for the
            # model in values[-2]. That will be used after generating
            # the joins here.
            for relation in values[:-1]:
                rel_field = getattr(rel_model, relation)
                rel_model = rel_field.property.mapper.class_
                self.query = self.query.join(rel_model)

            # Rename the field from table1__table2__field to field
            relation = values[-1]

        return (relation, rel_model)

    def render(self):
        """Generates SQLAlchemy query based on provided options and filters.

        :returns: Query
        """

        # Fields defines which field(s) will be included in query
        if self.options.get('fields'):
            fields = [getattr(self.model, f) for f in self.options['fields']]
            self.query = db().query(*fields)
        elif self.options.get('distinct'):
            fields = [
                getattr(self.model, f).distinct()
                for f in self.options['distinct']
            ]
            self.query = db().query(*fields)
        else:
            self.query = db().query(self.model)

        for f in self.filters:
            if isinstance(f, BoolFilter):
                filtered_exprs = [self._expand_filter(fil) for fil in f.filters]
                if f.type == 'or':
                    self.query = self.query.filter(or_(*filtered_exprs))
                if f.type == 'and':
                    self.query = self.query.filter(and_(*filtered_exprs))
                elif f.type == 'not':
                    self.query = self.query.filter(
                        not_(self._create_sa_filter(f.filters[0]))
                    )
            else:
                # If it's not a BoolFilter then it must be a filter using one
                # of the supported functions. In that case any relationships
                # need to be turned into join() statements and the appropriate
                # BinaryExpression will be created and passed to filter().
                relation, rel_model = self._expand_relation(f)
                op_func = self._create_sa_filter(
                    f, model=rel_model, relation=relation
                )
                self.query = self.query.filter(op_func)

        if self.options.get('order_by'):
            self._create_order_by(self.options['order_by'])

        if self.options.get('single'):
            self.query = self.query.first()

        return self.query


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
