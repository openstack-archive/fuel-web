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

import netaddr


def is_same_mac(mac1, mac2):
    """Check that two MACs are the same.

    It uses netaddr.EUI to represent MAC address. In case
    of wrong/unknown format of MAC address, raises ValueError
    """
    try:
        return netaddr.EUI(mac1) == netaddr.EUI(mac2)
    except netaddr.AddrFormatError as e:
        raise ValueError(e)
