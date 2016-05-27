# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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

import collections

from nailgun.settings import settings


class Rule(object):

    def __init__(self, component_name, numa_id=None, max_cpus=None,
                 min_cpus=0, take_all=False):
        self.component_name = component_name
        self.numa_id = numa_id
        self.max_cpus = max_cpus
        self.min_cpus = min_cpus
        self.take_all = take_all
        self.allocated = 0

    def get_numa_id(self, numas_cpus):
        if self.numa_id is None:
            return max(enumerate(numas_cpus), key=lambda tup: len(tup[1]))[0]
        return self.numa_id

    def get_consume_count(self, cpus_count, required):
        consume = min(required, 1)
        if self.take_all:
            consume = min(required, cpus_count)
        if self.max_cpus is not None:
            consume = min(consume, self.max_cpus - self.allocated)

        return consume


class CPUsConsumer(object):
    """Consume CPUs according to chunks rules

    chunk: {
        required: <number>,
        rules: [<rule>, ...]
    }
    """

    def __init__(self, numas_cpus):
        self.numas_cpus = numas_cpus
        self.chunks = collections.deque()
        self.result = {}
        self.cpus = []

    def add(self, chunks):
        for chunk in chunks:
            self.chunks.append(chunk)

    def consume(self):
        remained = 0
        while self.chunks:
            remained += self._consume_chunk(self.chunks.popleft())
        return remained

    def _consume_chunk(self, chunk):
        required = chunk['required']
        while required > 0:
            consumed = False
            for rule in chunk['rules']:
                numa_id = rule.get_numa_id(self.numas_cpus)

                length = len(self.numas_cpus[numa_id])
                consume = rule.get_consume_count(length, required)

                if consume == 0:
                    continue

                if length < consume:
                    raise ValueError(
                        "Failed to consume CPUs for '{0}':"
                        " try to consume {1} CPUs from NUMA {2}."
                        .format(rule.component_name, consume, numa_id))

                result = self.result.setdefault(rule.component_name, [])
                result.extend(self.numas_cpus[numa_id][:consume])
                self.cpus.extend(self.numas_cpus[numa_id][:consume])
                self.numas_cpus[numa_id] = self.numas_cpus[numa_id][consume:]

                required -= consume
                rule.allocated += consume
                consumed = True

            if not consumed:
                break

        for rule in chunk['rules']:
            if rule.allocated < rule.min_cpus:
                raise ValueError(
                    "Failed to consume CPUs for '{0}': at least {1} CPUs are"
                    " required, but {2} CPUs were allocated, try to specify"
                    " more CPUs or change configuration."
                    .format(rule.component_name, rule.min_cpus,
                            rule.allocated))
        return required


def _make_dpdk_chunks(cpus_consumer, dpdk_info, nics_numas):
    if not dpdk_info or dpdk_info['required_cpus'] == 0:
        return []
    if not nics_numas:
        raise ValueError(
            "DPDK CPUs distribution error: there is no"
            " any configured DPDK interface")

    required = dpdk_info['required_cpus']
    # currently there is requirements that ovs_core_mask
    # should contain 1 CPU
    core_chunk = {
        'required': 1,
        'rules': [
            Rule('ovs_core_mask', numa_id=nics_numas[0],
                 min_cpus=1, max_cpus=1)
        ]
    }

    required -= 1
    threads_chunk = {
        'required': required,
        'rules': []
    }
    for nic_numa in nics_numas:
        threads_chunk['rules'].append(
            Rule('ovs_pmd_core_mask', numa_id=nic_numa, min_cpus=1,
                 max_cpus=settings.DPDK_MAX_CPUS_PER_NIC)
        )

    return [core_chunk,
            threads_chunk]


def _make_nova_chunks(cpus_consumer, nova_info, dpdk_additional, numa_cpus):
    if not nova_info:
        return []
    sorted_numas = sorted(
        ((len(cpus), i) for i, cpus in enumerate(numa_cpus)),
        key=lambda tup: tup[0],
        reverse=True)
    needed_numas = []
    cpus_number = 0
    total_required = nova_info['required_cpus'] + dpdk_additional
    for count, numa_id in sorted_numas:
        if cpus_number >= total_required:
            break
        cpus_number += count
        needed_numas.append(numa_id)

    if cpus_number < total_required:
        raise ValueError(
            "Not enough CPUs for nova and additional dpdk:"
            " total required {0} actual {1}"
            .format(total_required, cpus_number))

    dpdk_additional_chunk = {
        'required': dpdk_additional,
        'rules': [],
    }
    for numa_id in needed_numas:
        dpdk_additional_chunk['rules'].append(
            Rule('ovs_pmd_core_mask', numa_id=numa_id)
        )

    nova_chunk = {
        'required': nova_info['required_cpus'],
        'rules': [],
    }
    for numa_id in needed_numas:
        nova_chunk['rules'].append(
            Rule('nova', numa_id=numa_id, take_all=True)
        )

    return [dpdk_additional_chunk,
            nova_chunk]


def _make_components_chunks(cpus_consumer, components):
    chunk = {
        'required': 0,
        'rules': []
    }
    for component in components.itervalues():
        chunk['required'] += component['required_cpus']
        chunk['rules'].append(
            Rule(component['name'], max_cpus=component['required_cpus'],
                 take_all=True)
        )
    return [chunk]


def distribute_node_cpus(numa_nodes, components, nics_numas):
    """Distribute CPUs accross components

    :param numa_nodes: information about numa nodes from node.meta
    :type numa_nodes: dict
    :param components: information about CPUs requirements per component
    :type components: dict
    :param nics_numas: information about dpdk nics NUMA affinity
    :type nics_numas: list[int]
    :return: dict with CPUs distribution
    """

    numa_cpus = []
    for numa in sorted(numa_nodes, key=lambda n: n['numa_id']):
        numa_cpus.append(numa['cpus'][:])

    cpus_consumer = CPUsConsumer(numa_cpus)

    cpus_consumer.add(_make_dpdk_chunks(
        cpus_consumer, components.pop('dpdk', None), nics_numas))
    dpdk_surplus = cpus_consumer.consume()

    cpus_consumer.add(_make_nova_chunks(
        cpus_consumer, components.pop('nova', None), dpdk_surplus, numa_cpus))
    cpus_consumer.add(_make_components_chunks(cpus_consumer, components))
    remained = cpus_consumer.consume()

    if remained != 0:
        raise ValueError(
            "Not all required CPUs were distributed: remained CPUs {0} - {1},"
            " distributed info {2}."
            .format(remained, numa_cpus, cpus_consumer.result))

    return {
        'isolated_cpus': sorted(cpus_consumer.cpus),
        'components': cpus_consumer.result
    }
