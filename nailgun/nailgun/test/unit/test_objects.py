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

import copy
from itertools import cycle
from itertools import ifilter

from nailgun.test.base import BaseIntegrationTest

from nailgun import consts

from nailgun.db import NoCacheQuery

from nailgun import objects


class TestObjects(BaseIntegrationTest):

    def test_filtering(self):
        names = cycle('ABCD')
        os = cycle(['CentOS', 'Ubuntu'])
        for i in xrange(12):
            self.env.create_release(
                name=names.next(),
                operating_system=os.next()
            )

        # filtering query - returns query
        query_filtered = objects.ReleaseCollection.filter_by(
            objects.ReleaseCollection.all(),
            name="A",
            operating_system="CentOS"
        )
        self.assertIsInstance(query_filtered, NoCacheQuery)
        self.assertEqual(
            objects.ReleaseCollection.count(query_filtered),
            3
        )
        for r in query_filtered:
            self.assertEqual(r.name, "A")
            self.assertEqual(r.operating_system, "CentOS")

        # filtering iterable - returns ifilter
        iterable_filtered = objects.ReleaseCollection.filter_by(
            list(objects.ReleaseCollection.all()),
            name="A",
            operating_system="CentOS"
        )
        self.assertIsInstance(iterable_filtered, ifilter)
        self.assertEqual(
            objects.ReleaseCollection.count(iterable_filtered),
            3
        )
        for r in iterable_filtered:
            self.assertEqual(r.name, "A")
            self.assertEqual(r.operating_system, "CentOS")


class TestNodeObject(BaseIntegrationTest):

    def test_adding_to_cluster_kernel_params_centos(self):
        self.env.create(
            release_kwargs={
                "operating_system": consts.RELEASE_OS.centos
            },
            cluster_kwargs={},
            nodes_kwargs=[
                {"role": "controller"}
            ]
        )
        node_db = self.env.nodes[0]
        self.assertEqual(
            node_db.kernel_params,
            (
                'console=ttyS0,9600 '
                'console=tty0 '
                'biosdevname=0 '
                'crashkernel=none '
                'rootdelay=90 '
                'nomodeset'
            )
        )

    def test_adding_to_cluster_kernel_params_ubuntu(self):
        self.env.create(
            release_kwargs={
                "operating_system": consts.RELEASE_OS.ubuntu,
                "attributes_metadata": {
                    "editable": {
                        "kernel_params": {
                            "kernel": {
                                "value": (
                                    "console=ttyS0,9600 "
                                    "console=tty0 "
                                    "rootdelay=90 "
                                    "nomodeset"
                                )
                            }
                        }
                    }
                }
            },
            cluster_kwargs={},
            nodes_kwargs=[
                {"role": "controller"}
            ]
        )
        node_db = self.env.nodes[0]
        self.assertEqual(
            node_db.kernel_params,
            (
                'console=ttyS0,9600 '
                'console=tty0 '
                'rootdelay=90 '
                'nomodeset'
            )
        )

    def test_removing_from_cluster(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"role": "controller"}
            ]
        )
        node_db = self.env.nodes[0]
        node2_db = self.env.create_node()
        objects.Node.remove_from_cluster(node_db)
        self.assertEqual(node_db.cluster_id, None)
        self.assertEqual(node_db.roles, [])
        self.assertEqual(node_db.pending_roles, [])

        exclude_fields = [
            "id",
            "mac",
            "meta",
            "name",
            "agent_checksum"
        ]
        fields = set(
            objects.Node.schema["properties"].keys()
        ) ^ set(exclude_fields)

        for f in fields:
            self.assertEqual(
                getattr(node_db, f),
                getattr(node2_db, f)
            )

    def test_removing_from_cluster_idempotent(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"role": "controller"}
            ]
        )
        node_db = self.env.nodes[0]
        objects.Node.remove_from_cluster(node_db)

        try:
            objects.Node.remove_from_cluster(node_db)
        except Exception as exc:
            self.fail("Node removing is not idempotent: {0}!".format(exc))

    def test_update_by_agent(self):
        node_db = self.env.create_node()
        data = {
            "status": node_db.status,
            "meta": copy.deepcopy(node_db.meta),
            "mac": node_db.mac,
        }

        # test empty disks handling
        data["meta"]["disks"] = []
        objects.Node.update_by_agent(node_db, copy.deepcopy(data))
        self.assertNotEqual(node_db.meta["disks"], data["meta"]["disks"])

        # test status handling
        for status in ('provisioning', 'error'):
            node_db.status = status
            data["status"] = "discover"
            objects.Node.update_by_agent(node_db, copy.deepcopy(data))

            self.assertEqual(node_db.status, status)

    def test_eager_nodes_handlers(self):
        """Test verifies that custom handler works and returns correct
        number of nodes.
        """
        nodes_count = 10
        self.env.create_nodes(nodes_count)
        nodes_db = objects.NodeCollection.eager_nodes_handlers(None)
        self.assertEqual(nodes_db.count(), nodes_count)
