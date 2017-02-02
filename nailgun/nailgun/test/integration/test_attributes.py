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

from oslo_serialization import jsonutils
import six

from nailgun import consts
from nailgun.db.sqlalchemy.models import Release
from nailgun import objects
from nailgun.settings import settings
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestClusterAttributes(BaseIntegrationTest):

    ATTRIBUTES_WITH_RESTRICTIONS = {
        'editable': {
            'test': {
                'comp1': {
                    'description': 'desc',
                    'label': 'Comp 1',
                    'type': 'checkbox',
                    'value': False,
                    'weight': 10,
                },
                'comp2': {
                    'description': 'desc',
                    'label': 'Comp 2',
                    'type': 'checkbox',
                    'value': False,
                    'weight': 20,
                    'restrictions': ["settings:test.comp1.value == true"],
                },
                'comp3': {
                    'description': 'desc',
                    'label': 'Comp 3',
                    'type': 'text',
                    'value': '',
                    'weight': 30,
                    'restrictions': [
                        {
                            'condition': "settings:test.comp1.value == true",
                            'action': "disable"
                        }
                    ],
                    'regex': {
                        'source': '^[a-zA-Z\d][a-zA-Z\d_\-.]+(:[0-9]+)?$',
                        'error': "Wrong Comp 3 value"
                    }
                }
            }
        }
    }

    def test_attributes_creation(self):
        cluster = self.env.create_cluster(api=True)
        resp = self.app.get(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster['id']}),
            headers=self.default_headers
        )
        release = objects.Release.get_by_uid(cluster['release_id'])
        self.assertEqual(200, resp.status_code)
        self._compare_editable(
            release.attributes_metadata['editable'],
            resp.json_body['editable'],
            cluster
        )
        attrs = objects.Cluster.get_attributes(cluster)
        self._compare_generated(
            release.attributes_metadata['generated'],
            attrs['generated'],
            cluster
        )

    def test_500_if_no_attributes(self):
        cluster = self.env.create_cluster(api=False)
        self.db.delete(cluster.attributes)
        self.db.commit()
        resp = self.app.put(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster.id}),
            params=jsonutils.dumps({
                'editable': {
                    "foo": "bar"
                },
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(500, resp.status_code)

    def test_attributes_update_put(self):
        cluster = self.env.create_cluster(api=True)
        cluster_id = cluster['id']
        resp = self.app.get(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster_id}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        resp = self.app.put(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster_id}),
            params=jsonutils.dumps({
                'editable': {
                    'foo': {'bar': None}
                },
            }),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        attrs = objects.Cluster.get_editable_attributes(cluster)
        self.assertEqual({'bar': None}, attrs["foo"])
        attrs.pop('foo')

        # 400 on generated update
        resp = self.app.put(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster_id}),
            params=jsonutils.dumps({
                'generated': {
                    "foo": "bar"
                },
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
        # 400 if editable is not dict
        resp = self.app.put(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster_id}),
            params=jsonutils.dumps({
                'editable': ["foo", "bar"],
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)

    def test_attributes_update_patch(self):
        cluster = self.env.create_cluster(api=True)
        resp = self.app.get(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster['id']}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        resp = self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster['id']}),
            params=jsonutils.dumps({
                'editable': {
                    'foo': {'bar': None}
                },
            }),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        attrs = objects.Cluster.get_editable_attributes(cluster)
        self.assertEqual({'bar': None}, attrs["foo"])
        attrs.pop('foo')
        self.assertNotEqual(attrs, {})

    def test_failing_attributes_put(self):
        cluster_id = self.env.create_cluster(api=True)['id']
        resp = self.app.get(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster_id}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        resp = self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster_id}),
            params=jsonutils.dumps({
                'editable': {
                    'storage': {
                        'osd_pool_size': {
                            'description': 'desc',
                            'label': 'OSD Pool Size',
                            'type': 'text',
                            'value': True,
                            'weight': 80,
                        },
                    },
                },
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)

    def test_failing_attributes_with_restrictions(self):
        cluster = self.env.create_cluster(api=False)
        objects.Cluster.patch_attributes(
            cluster, self.ATTRIBUTES_WITH_RESTRICTIONS)

        resp = self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster.id}),
            params=jsonutils.dumps({
                'editable': {
                    'test': {
                        'comp1': {
                            'value': True
                        },
                        'comp2': {
                            'value': True
                        }
                    }
                }
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)

        extended_restr = {
            'condition': "settings:test.comp1.value == true",
            'action': 'disable',
        }
        self.assertIn(
            "Validation failed for attribute 'Comp 2': restriction with action"
            "='{}' and condition='{}' failed due to attribute value='True'"
            .format(extended_restr['action'], extended_restr['condition']),
            resp.json_body['message'])

    def test_disabled_attributes_with_restrictions_not_fail(self):
        cluster = self.env.create_cluster(api=False)
        objects.Cluster.patch_attributes(
            cluster, self.ATTRIBUTES_WITH_RESTRICTIONS)

        resp = self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster.id}),
            params=jsonutils.dumps({
                'editable': {
                    'test': {
                        'comp1': {
                            'value': True
                        },
                        'comp3': {
                            'value': ''
                        }
                    }
                }
            }),
            headers=self.default_headers
        )

        self.assertEqual(200, resp.status_code)

    def test_enabled_attributes_raise_regex_exception(self):
        cluster = self.env.create_cluster(api=False)
        objects.Cluster.patch_attributes(
            cluster, self.ATTRIBUTES_WITH_RESTRICTIONS)

        resp = self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster.id}),
            params=jsonutils.dumps({
                'editable': {
                    'test': {
                        'comp1': {
                            'value': False
                        },
                        'comp3': {
                            'value': ''
                        }
                    }
                }
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
        self.assertEqual(
            "Some restrictions didn't pass verification: "
            "['Wrong Comp 3 value']",
            resp.json_body['message']
        )

    def test_get_default_attributes(self):
        cluster = self.env.create_cluster(api=True)
        release = self.db.query(Release).get(
            cluster['release_id']
        )
        resp = self.app.put(
            reverse(
                'ClusterAttributesDefaultsHandler',
                kwargs={'cluster_id': cluster['id']}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self._compare_editable(
            release.attributes_metadata['editable'],
            resp.json_body['editable'],
            cluster
        )

    def test_get_last_deployed_attributes(self):
        cluster = self.env.create_cluster(api=True)
        cluster_attrs = objects.Cluster.get_editable_attributes(
            self.env.clusters[-1]
        )
        transaction = objects.Transaction.create({
            'cluster_id': cluster.id,
            'status': consts.TASK_STATUSES.ready,
            'name': consts.TASK_NAMES.deployment
        })
        objects.Transaction.attach_cluster_settings(
            transaction, {'editable': cluster_attrs}
        )
        self.assertIsNotNone(
            objects.TransactionCollection.get_last_succeed_run(cluster)
        )
        resp = self.app.get(
            reverse(
                'ClusterAttributesDeployedHandler',
                kwargs={'cluster_id': cluster.id}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.datadiff(cluster_attrs, resp.json_body['editable'])

    def test_get_deployed_attributes_fails_if_no_attrs(self):
        cluster = self.env.create_cluster(api=True)
        resp = self.app.get(
            reverse(
                'ClusterAttributesDeployedHandler',
                kwargs={'cluster_id': cluster['id']}),
            headers=self.default_headers,
            expect_errors=True,
        )
        self.assertEqual(404, resp.status_code)

    def test_attributes_set_defaults(self):
        cluster = self.env.create_cluster(api=True)
        # Change editable attributes.
        resp = self.app.put(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster['id']}),
            params=jsonutils.dumps({
                'editable': {
                    'foo': {'bar': None}
                },
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(200, resp.status_code, resp.body)
        attrs = objects.Cluster.get_editable_attributes(cluster)
        self.assertEqual({'bar': None}, attrs['foo'])
        # Set attributes to defaults.
        resp = self.app.put(
            reverse(
                'ClusterAttributesDefaultsHandler',
                kwargs={'cluster_id': cluster['id']}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        release = self.db.query(Release).get(
            cluster['release_id']
        )
        self._compare_editable(
            release.attributes_metadata['editable'],
            resp.json_body['editable'],
            cluster
        )

    def test_attributes_merged_values(self):
        cluster = self.env.create_cluster(api=True)
        cluster_db = objects.Cluster.get_by_uid(cluster['id'])
        orig_attrs = objects.Attributes.merged_attrs(cluster_db.attributes)
        attrs = objects.Attributes.merged_attrs_values(cluster_db.attributes)
        for group, group_attrs in six.iteritems(orig_attrs):
            for attr, orig_value in six.iteritems(group_attrs):
                if group == 'common':
                    value = attrs[attr]
                elif group == 'additional_components':
                    for c, val in six.iteritems(group_attrs):
                        self.assertIn(c, attrs)
                        if 'value' in val:
                            self.assertEqual(val["value"],
                                             attrs[c]["enabled"])
                    continue
                else:
                    value = attrs[group][attr]
                if isinstance(orig_value, dict) and 'value' in orig_value:
                    self.assertEqual(orig_value['value'], value)
                else:
                    self.assertEqual(orig_value, value)

    def _compare_generated(self, d1, d2, cluster):
        if isinstance(d1, dict) and isinstance(d2, dict):
            for s_field, s_value in six.iteritems(d1):
                if s_field not in d2:
                    raise KeyError()
                self._compare_generated(s_value, d2[s_field], cluster)
        elif isinstance(d1, six.string_types):
            if d1 in [u"", ""]:
                self.assertEqual(len(d2), 8)
            else:
                self.assertEqual(
                    d1.format(settings=settings, cluster=cluster),
                    d2.format(settings=settings, cluster=cluster))

    def _compare_editable(self, r_attrs, c_attrs, cluster=None):
        """Compare editable attributes omitting the check of generated values

        :param r_attrs: attributes from release
        :param c_attrs: attributes from cluster
        """
        # TODO(ikalnitsky):
        # This code should be rewritten completely. We have to use one
        # function for comparing both generated and editable attributes.
        # Moreover, I'm not sure we have keep that code, since it duplicated
        # traverse function in many cases.
        if isinstance(r_attrs, dict) and isinstance(c_attrs, dict):
            for s_field, s_value in six.iteritems(r_attrs):
                if s_field not in c_attrs:
                    self.fail("'{0}' not found in '{1}'".format(s_field,
                                                                c_attrs))
                if s_field != 'regex':
                    self._compare_editable(s_value, c_attrs[s_field], cluster)
                else:
                    self.assertEqual(s_value, c_attrs[s_field])
        elif isinstance(r_attrs, (list, tuple)) and \
                isinstance(c_attrs, (list, tuple)):
            if len(r_attrs) != len(c_attrs):
                self.fail('Different number of elements: {0} vs {1}'.format(
                    c_attrs, r_attrs))
            for index in range(0, len(r_attrs)):
                self._compare_editable(r_attrs[index], c_attrs[index], cluster)
        elif isinstance(c_attrs, six.string_types + (list, tuple)) and \
                isinstance(r_attrs, dict):
            self.assertIn("generator", r_attrs)
        elif isinstance(c_attrs, six.string_types) and \
                isinstance(r_attrs, six.string_types):
            self.assertEqual(
                c_attrs, r_attrs.format(settings=settings, cluster=cluster))
        else:
            self.assertEqual(c_attrs, r_attrs)

    def test_compare_editable(self):
        r_attrs = {
            'section1': {
                'value': 'string1'
            },
            'section2': {
                'subsection1': {
                    'value': 'string2'
                }
            }
        }
        c_attrs = {
            'section1': {
                'value': 'string1'
            },
            'section2': {
                'subsection1': {
                    'value': 'string2'
                }
            }
        }
        self._compare_editable(r_attrs, c_attrs)

        r_attrs['section1']['value'] = {
            'generator': 'generator1'
        }
        self._compare_editable(r_attrs, c_attrs)

        r_attrs['section2']['subsection1']['value'] = {
            'generator': 'generator2'
        }
        self._compare_editable(r_attrs, c_attrs)

        r_attrs['section1']['value'] = 'zzzzzzz'
        self.assertRaises(
            AssertionError, self._compare_editable, r_attrs, c_attrs)

    def test_editable_attributes_generators(self):
        cluster = self.env.create_cluster(api=True)
        editable = objects.Cluster.get_editable_attributes(cluster)
        self.assertEqual(
            editable["external_dns"]["dns_list"]["value"],
            settings.DNS_UPSTREAM
        )
        self.assertEqual(
            editable["external_ntp"]["ntp_list"]["value"],
            settings.NTP_UPSTREAM
        )

    def test_workloads_collector_attributes(self):
        cluster = self.env.create_cluster(api=True)
        editable = objects.Cluster.get_editable_attributes(cluster)
        self.assertEqual(
            editable["workloads_collector"]["enabled"]["value"],
            True
        )
        self.assertEqual(
            editable["workloads_collector"]["user"]["value"],
            "fuel_stats_user"
        )
        self.assertEqual(
            editable["workloads_collector"]["tenant"]["value"],
            "services"
        )
        self.assertEqual(
            len(editable["workloads_collector"]["password"]["value"]),
            24
        )
        self.assertEqual(
            set(editable["workloads_collector"]["metadata"].keys()),
            set(["label", "weight", "restrictions", "group"])
        )


class TestAlwaysEditable(BaseIntegrationTest):

    _reposetup = {
        'repo_setup': {
            'metadata': {
                'label': 'Repositories',
                'weight': 50,
            },
            'repos': {
                'type': 'custom_repo_configuration',
                'extra_priority': 15,
                'value': [
                    {
                        'type': 'rpm',
                        'name': 'mos',
                        'uri': 'http://127.0.0.1:8080/myrepo'
                    }
                ]
            }
        }}

    def setUp(self):
        super(TestAlwaysEditable, self).setUp()
        self.cluster = self.env.create(
            release_kwargs={
                'version': 'liberty-8.0',
                'operating_system': consts.RELEASE_OS.centos})

    def _put(self, data, expect_code=200):
        resp = self.app.put(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': self.cluster['id']}),
            params=jsonutils.dumps(data),
            expect_errors=True,
            headers=self.default_headers)
        self.assertEqual(expect_code, resp.status_code)
        return resp.json_body

    def test_can_change_repos_on_operational_cluster(self):
        self.cluster.status = consts.CLUSTER_STATUSES.operational
        self.db.flush()
        self.assertFalse(self.cluster.is_locked)

        data = {'editable': {}}
        data['editable'].update(self._reposetup)

        self._put(data, expect_code=200)

        attrs = self.cluster.attributes.editable
        self.assertEqual(attrs['repo_setup']['repos']['value'], [{
            'type': 'rpm',
            'name': 'mos',
            'uri': 'http://127.0.0.1:8080/myrepo',
        }])


class TestAttributesWithPlugins(BaseIntegrationTest):

    def setUp(self):
        super(TestAttributesWithPlugins, self).setUp()

        self.cluster = self.env.create(
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': '2015.1.0-7.0',
            },
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.vlan,
            },
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True},
            ]
        )

        self.plugin_data = {
            'releases': [
                {
                    'repository_path': 'repositories/ubuntu',
                    'version': self.cluster.release.version,
                    'os': self.cluster.release.operating_system.lower(),
                    'mode': [self.cluster.mode],
                }
            ]
        }

    def test_cluster_contains_plugins_attributes(self):
        self.env.create_plugin(cluster=self.cluster, **self.plugin_data)
        resp = self.app.get(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': self.cluster['id']}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertIn('testing_plugin', resp.json_body['editable'])

    def test_change_plugins_attributes(self):
        plugin = self.env.create_plugin(cluster=self.cluster,
                                        **self.plugin_data)

        def _modify_plugin(enabled=True):
            return self.app.put(
                reverse(
                    'ClusterAttributesHandler',
                    kwargs={'cluster_id': self.cluster['id']}),
                params=jsonutils.dumps({
                    'editable': {
                        plugin.name: {
                            'metadata': {
                                'class': 'plugin',
                                'label': 'Test plugin',
                                'toggleable': True,
                                'weight': 70,
                                'enabled': enabled,
                                'chosen_id': plugin.id,
                                'versions': [{
                                    'metadata': {
                                        'plugin_id': plugin.id,
                                        'plugin_version': plugin.version
                                    },
                                    'attr': {
                                        'type': 'text',
                                        'description': 'description',
                                        'label': 'label',
                                        'value': '1',
                                        'weight': 25,
                                        'restrictions': [{
                                            'condition': 'true',
                                            'action': 'hide'}]
                                    }
                                }]
                            },
                        }
                    }
                }),
                headers=self.default_headers
            )

        resp = _modify_plugin(enabled=True)
        self.assertEqual(200, resp.status_code)
        editable = objects.Cluster.get_editable_attributes(self.cluster)
        self.assertIn(plugin.name, editable)
        self.assertTrue(editable[plugin.name]['metadata']['enabled'])
        self.assertEqual('1', editable[plugin.name]['attr']['value'])

        resp = _modify_plugin(enabled=False)
        self.assertEqual(200, resp.status_code)
        editable = objects.Cluster.get_editable_attributes(self.cluster)
        self.assertNotIn(plugin.name, editable)

    def _modify_plugin(self, plugin, enabled):
        return self.app.put(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': self.cluster.id}
            ),
            params=jsonutils.dumps({
                'editable': {
                    plugin.name: {
                        'metadata': {
                            'class': 'plugin',
                            'enabled': enabled,
                            'chosen_id': plugin.id,
                            'versions': [{
                                'metadata': {
                                    'plugin_id': plugin.id,
                                    'plugin_version': plugin.version
                                }
                            }]
                        }
                    }
                }
            }),
            headers=self.default_headers,
            expect_errors=True
        )

    def test_install_plugins_after_deployment(self):
        self.cluster.status = consts.CLUSTER_STATUSES.operational
        self.assertFalse(self.cluster.is_locked)
        runtime_plugin = self.env.create_plugin(
            cluster=self.cluster,
            is_hotpluggable=True,
            version='1.0.1',
            enabled=False,
            **self.plugin_data
        )
        resp = self._modify_plugin(runtime_plugin, True)
        self.assertEqual(200, resp.status_code, resp.body)
        editable = objects.Cluster.get_editable_attributes(self.cluster)
        self.assertIn(runtime_plugin.name, editable)
        self.assertTrue(editable[runtime_plugin.name]['metadata']['enabled'])

    def test_enable_plugin_is_idempotent(self):
        plugin = self.env.create_plugin(
            cluster=self.cluster,
            version='1.0.1',
            is_hotpluggable=True,
            enabled=True,
            **self.plugin_data
        )

        self.cluster.status = consts.CLUSTER_STATUSES.operational
        self.assertFalse(self.cluster.is_locked)
        resp = self._modify_plugin(plugin, True)
        self.assertEqual(200, resp.status_code, resp.body)
