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

from six import moves as six_moves


def get_fake_interface_config(iface=None, iface_id=None, state=None, mac=None,
                              iface_type=None, networks=None):
    """Create a random fake interface configuration

    Returns the serialized and parametrized representation of a node's
    interface configuration. Represents the average amount of data.

    """

    return {"name": iface or "eth0",
            "id": iface_id or random.randint(0, 1000),
            "state": state or "unknown",
            "mac": mac or "08:00:27:a4:01:6b",
            "max_speed": 100,
            "type": iface_type or "ether",
            "current_speed": 100,
            "assigned_networks": networks or [{"id": 1,
                                               "name": "fuelweb_admin"},
                                              {"id": 3,
                                               "name": "management"},
                                              {"id": 4,
                                               "name": "storage"},
                                              {"id": 5,
                                               "name": "fixed"}]}


def get_fake_network_config(iface_number):
    """Creates a fake network configuration for a single node."""

    return [get_fake_interface_config(iface='eth{0}'.format(i))
            for i in six_moves.range(iface_number)]
