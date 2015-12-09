from nailgun.db.sqlalchemy import models
from nailgun.network.proxy.utils import BoolFilter
from nailgun.network.proxy.utils import Filter
from nailgun.network.proxy.utils import Query
from nailgun.test.base import BaseTestCase


class TestQueryBuilder(BaseTestCase):

    def setUp(self):
        super(TestQueryBuilder, self).setUp()

    def test_create_sa_filter(self):
        data = {
            'filters': [
                {'name': 'id', 'op': 'eq', 'val': 1}
            ]
        }
        query = Query(models.NetworkGroup, data)
        sa_filter = query._create_sa_filter(query.filters[0])

        self.assertEqual(sa_filter.left.name, 'id')
        self.assertEqual(sa_filter.right.value, 1)
        self.assertEqual(sa_filter.operator.__name__, 'eq')

    def test_create_order_by(self):
        self.env.create_node(name='node-1')
        self.env.create_node(name='node-2')

        data = {
            'options': {
                'order_by': ['name']
            }
        }
        query = Query(models.Node, data)
        nodes = query.render().all()

        self.assertEqual(nodes[0].name, 'node-1')
        self.assertEqual(nodes[1].name, 'node-2')

        data['options']['order_by'] = ['-name']
        query = Query(models.Node, data)
        nodes = query.render().all()

        self.assertEqual(nodes[0].name, 'node-2')
        self.assertEqual(nodes[1].name, 'node-1')

    def test_expand_relation(self):
        data = {
            'filters': [
                {'name': 'nodegroup__cluster_id', 'op': 'eq', 'val': 1}
            ]
        }
        query = Query(models.Node, data)

        relation, rel_model = query._expand_relation(query.filters[0])
        self.assertEqual(relation, 'cluster_id')
        self.assertEqual(rel_model, models.NodeGroup)

    def test_expand_filter(self):
        data = {
            'filters': [
                {
                    'or': [
                        {'name': 'name', 'op': 'eq', 'val': 'test'},
                        {'name': 'id', 'op': 'in', 'val': [1, 2]}
                    ]
                },
                {'name': 'cidr', 'op': 'ne', 'val': '1.2.3.4'}
            ]
        }

        query = Query(models.NetworkGroup, data)
        filter = query._expand_filter(query.filters[0])
        clauses = filter.clauses
        self.assertEqual(len(clauses), 2)
        self.assertEqual(filter.operator.__name__, 'or_')

        self.assertEqual(clauses[0].left.name, 'name')
        self.assertEqual(clauses[0].right.value, 'test')
        self.assertEqual(clauses[0].operator.__name__, 'eq')

    def test_filter_from_dict(self):
        data = [
            {
                'or': [
                    {'name': 'name', 'op': 'eq', 'val': 'test'},
                    {'name': 'id', 'op': 'in', 'val': [1, 2]}
                ]
            },
            {'name': 'cidr', 'op': 'ne', 'val': '1.2.3.4'}
        ]

        filter = Filter.from_dict(data[0])
        self.assertEqual(type(filter), BoolFilter)
        self.assertEqual(len(filter.filters), 2)

        filter = Filter.from_dict(data[1])
        self.assertEqual(type(filter), Filter)
        self.assertEqual(filter.op, 'ne')


class TestProxy(BaseTestCase):
    def setUp(self):
        super(TestProxy, self).setUp()

        self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'role': 'controller'}])
        self.cluster = self.env.clusters[0]
