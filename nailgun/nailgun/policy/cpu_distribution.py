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

import itertools

KNOWN_GROUPS = {"nova": "nova_dpdk", "dpdk": "nova_dpdk"}


class CpuDistributor(object):
    def __init__(self, component):
        self.name = component['name']
        self.cpus = component.get('cpus', [])
        self.required = component['required_cpus']

    def consume(self, cpus, limit=None):
        """Assign required number of cpus

        :param cpus: list of available cpu ids
        :param limit: limit of cpus that can be taken
        :return: False if no more cpus needed
        """
        required = min(self.required, len(cpus))
        if limit is not None:
            required = min(required, limit)
        self.cpus.extend(cpus[:required])
        cpus[:] = cpus[required:]
        self.required -= required
        return self.required > 0


class CpuDistributorForGroup(object):
    def __init__(self, components):
        self.components = [CpuDistributor(c) for c in components]
        self.total_required = reduce(lambda x, y: x + y.required,
                                     self.components, 0)

    def consume(self, cpus):
        """Assign required number of cpus to components

        :param cpus: list of available cpu ids
        :return: False if no more cpus needed
        """
        remained_required = self.total_required
        cpus_len = len(cpus)

        for component in self.components:
            if remained_required <= 0:
                break
            if component.required <= 0:
                continue
            part = max(1, component.required * len(cpus) // remained_required)
            remained_required -= component.required
            component.consume(cpus, limit=part)

        self.total_required -= cpus_len - len(cpus)
        return self.total_required > 0

    def add_to_result(self, result):
        for component in self.components:
            result['isolated_cpus'].extend(component.cpus)
            result['components'][component.name] = component.cpus

        return result


def distribute_node_cpus(numa_nodes, components):
    # sort by component group or by name if the components in the same group
    group_func = lambda x: KNOWN_GROUPS.get(x['name'], x['name'])
    grouped_components = sorted(
        components,
        key=lambda x: (group_func(x), x['name']))

    numa_nodes_it = iter(numa_nodes)
    current_cpus = []
    result = {'isolated_cpus': [],
              'components': {}}

    for _, group in itertools.groupby(grouped_components, group_func):
        distributor = CpuDistributorForGroup(group)

        while True:
            if not current_cpus:
                current_cpus = next(numa_nodes_it)['cpus'][:]
            if not distributor.consume(current_cpus):
                break

        distributor.add_to_result(result)

    result['isolated_cpus'].sort()
    return result
