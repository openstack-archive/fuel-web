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

import os
from random import randint

from nailgun.db.sqlalchemy.fixman import load_fixture
from nailgun.logger import logger


def generate_random_mac():
    mac = [randint(0x00, 0x7f) for _ in xrange(6)]
    return ':'.join(map(lambda x: "%02x" % x, mac)).lower()


def find_item_by_pk_model(data, pk, model):
    for item in data:
        if item.get('pk') == pk and item.get('model') == model:
            return item


def read_fixtures(fxtr_names, fixture_dir):
    data = []
    for fxtr_path in fxtr_paths_by_names(fxtr_names, fixture_dir):
        with open(fxtr_path, "r") as fxtr_file:
            try:
                data.extend(load_fixture(fxtr_file))
            except Exception as exc:
                logger.error(
                    'Error "%s" occurred while loading '
                    'fixture %s' % (exc, fxtr_path)
                )
    return data


def fxtr_paths_by_names(fxtr_names, fixture_dir):
    for fxtr in fxtr_names:
        for ext in ['json', 'yaml']:
            fxtr_path = os.path.join(
                fixture_dir,
                "%s.%s" % (fxtr, ext)
            )

            if os.path.exists(fxtr_path):
                logger.debug(
                    "Fixture file is found, yielding path: %s",
                    fxtr_path
                )
                yield fxtr_path
                break
        else:
            logger.warning(
                "Fixture file was not found: %s",
                fxtr
            )


def default_metadata(fixture_dir):
    item = find_item_by_pk_model(
        read_fixtures(("sample_environment",), fixture_dir),
        1, 'nailgun.node')
    return item.get('fields').get('meta')


def generate_node_data(fixture_dir, exclude, **kwargs):
    metadata = kwargs.pop('meta', None)
    default_meta = default_metadata(fixture_dir)
    if metadata:
        default_meta.update(metadata)
        meta_ifaces = 'interfaces' in metadata

    mac = kwargs.get('mac', generate_random_mac())
    if default_meta['interfaces']:
        default_meta['interfaces'][0]['mac'] = mac
        if not metadata or not meta_ifaces:
            for iface in default_meta['interfaces'][1:]:
                if 'mac' in iface:
                    iface['mac'] = generate_random_mac()

    node_data = {
        'mac': mac,
        'status': 'discover',
        'ip': '10.20.0.130',
        'meta': default_meta
    }
    node_data.update(kwargs)

    if exclude and isinstance(exclude, list):
        for ex in exclude:
            try:
                del node_data[ex]
            except KeyError as err:
                logger.warning(err)
    return metadata, node_data
