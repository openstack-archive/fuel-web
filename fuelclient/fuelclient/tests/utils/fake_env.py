# -*- coding: utf-8 -*-
#
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

import random


def _generate_changes(number=None, node_ids=None):
    """Generates specified number of changes

    :param number:   Number of changes to create.
    :param node_ids: IDs of the nodes which are changed. If None, a linear
                     sequense [0, <number>) will be used. Number of IDs must
                     match the number of changes.
    :return:         list of dict

    """
    if (number is None) and (node_ids is None):
        raise ValueError("Either number of changes or Nodes' IDs is requied.")

    if node_ids is None:
        node_ids = range(number)

    change_types = ["networks", "interfaces", "disks", "attributes"]

    return [{"node_id": n_id, "name": random.choice(change_types)}
            for n_id in node_ids]


def get_fake_env(name=None, status=None, release_id=None, fuel_version=None,
                 pending_release=None, env_id=None, changes_number=None):
    """Create a random fake environment

    Returns the serialized and parametrized representation of a dumped Fuel
    environment. Represents the average amount of data.

    """
    return {"status": status or "new",
            "is_customized": False,
            "release_id": release_id or 1,
            "name": name or "fake_env",
            "grouping": "roles",
            "net_provider": "nova_network",
            "fuel_version": fuel_version or "5.1",
            "pending_release_id": pending_release,
            "id": env_id or 1,
            "mode": "multinode",
            "changes": _generate_changes(changes_number)}
