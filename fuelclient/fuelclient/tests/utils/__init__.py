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

from fuelclient.tests.utils.random_data import random_string
from fuelclient.tests.utils.fake_net_conf import get_fake_interface_config
from fuelclient.tests.utils.fake_net_conf import get_fake_network_config
from fuelclient.tests.utils.fake_node import get_fake_node
from fuelclient.tests.utils.fake_env import get_fake_env


__all__ = (get_fake_env,
           get_fake_node,
           random_string,
           get_fake_interface_config,
           get_fake_network_config)
