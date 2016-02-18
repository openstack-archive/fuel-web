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
import operator

import six

from nailgun import objects

KNOWN_GROUPS = {"nova": "nova_dpdk", "dpdk": "nova_dpdk"}


class CpuDistributor(object):
    def __init__(self, component):
        self.name = component['name']
        self.cpus = component.get('cpus', [])
        self.required = component['required_cpus']

    def consume(self, cpus):
        """Assign required number of cpus

        :param cpus: list of available cpu ids
        :return: False if no more cpus needed
        """
        self.cpus.extend(cpus[:self.required])
        self.required -= len(cpus)
        return self.required > 0


class CpuDistributorForGroup(object):
    def __init__(self, components):
        self.components = [CpuDistributor(c) for c in components]
        self.total_required = reduce(lambda x, y: x + y.required,
                                     self.components, 0)
        self.iter_cycle = itertools.cycle(self.components)

    def consume(self, cpus):
        """Assign required number of cpus to components

        :param cpus: list of available cpu ids
        :return: False if no more cpus needed
        """
        total_required = self.total_required
        self.total_required -= len(cpus)

        while cpus and total_required:
            component = next(self.iter_cycle)
            if component.required <= 0:
                continue
            part, _ = divmod(component.required * len(cpus),
                             total_required)
            part = min(component.required, max(1, part))
            total_required -= component.required
            component.consume(cpus[:part])
            cpus[:] = cpus[part:]

        return self.total_required > 0

    def to_dict(self):
        result = {'isolated_cpus': [],
                  'components': {}}

        for component in self.components:
            result['isolated_cpus'].extend(component.cpus)
            result['components'][component.name] = component.cpus

        return result


def distribute_node_cpus(node):
    components = sorted(
        six.itervalues(node_cpu_pinning_info(node)['components']),
        key=operator.itemgetter('name'))

    keyfunc = lambda x: KNOWN_GROUPS.get(x['name'], x['name'])
    grouped_components = sorted(components, key=keyfunc)

    numa_nodes_it = iter(node.meta['numa_topology']['numa_nodes'])
    current_cpus = []
    result = {'isolated_cpus': [],
              'components': {}}

    for _, group in itertools.groupby(grouped_components, keyfunc):
        distributor = CpuDistributorForGroup(group)

        while True:
            if not current_cpus:
                current_cpus = next(numa_nodes_it)['cpus']
            if not distributor.consume(current_cpus):
                break

        distribute_result = distributor.to_dict()
        result['isolated_cpus'].extend(distribute_result['isolated_cpus'])
        result['components'].update(distribute_result['components'])
    result['isolated_cpus'] = sorted(result['isolated_cpus'])
    return result


def node_cpu_pinning_info(node):
    total_required_cpus = 0
    components = {}
    cpu_pinning_attrs = objects.Node.get_attributes(node)['cpu_pinning']
    for name, attrs in six.iteritems(cpu_pinning_attrs):
        # skip meta
        if 'value' in attrs:
            required_cpus = int(attrs['value'])
            total_required_cpus += required_cpus
            components[name] = {'name': name,
                                'required_cpus': required_cpus}
    return {'total_required_cpus': total_required_cpus,
            'components': components}
