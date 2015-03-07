# -*- coding: UTF-8 -*-
#
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

ALLOWED_TO_FAIL = [{'name': 'compute', 'setting': 'max_computes_to_fail'}]


def for_provision(nodes, cluster_attrs):
    may_fail = []
    for role in ALLOWED_TO_FAIL:
        uids = []
        for node in nodes:
            if role['name'] in node.roles:
                uids.append(node.uid)
        percentage = cluster_attrs.get(role['setting'], 0)
        may_fail.append({'uids': uids,
                         'percentage': int(percentage)})
    return may_fail
