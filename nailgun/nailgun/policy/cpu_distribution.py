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


class CPUsConsumer(object):
    """Consume CPUs according to chunks rules

    chunk: {
        required: <number>,
        rules: [<rule>, ...]
    }
    rule: {
        numa_id: <number>, (optional)
        max_cpus: <number>, (optional)
        component_name: <string>,
        min_cpus: <number>, (optional)
        take_all: <bool>, (optional)
    }
    """

    def __init__(self):
        self.chunks = collections.deque()
        self.result = {}
        self.cpus = []

    def add(self, chunk):
        self.chunks.append(chunk)

    def consume(self, numas_cpus):
        remained = 0
        while self.chunks:
            remained += self._consume_chunk(self.chunks.popleft(), numas_cpus)
        return remained

    def _get_numa_id(self, rule, numas_cpus):
        return rule.get(
            'numa_id',
            max(enumerate(numas_cpus), key=lambda tup: len(tup[1]))[0]
        )

    def _get_consume_count(self, rule, cpus_count, required):
        allocated = rule.setdefault('allocated', 0)
        consume = min(required, 1)
        if rule.get('take_all'):
            consume = min(required, cpus_count)
        if 'max_cpus' in rule:
            consume = min(consume, rule['max_cpus'] - allocated)

        return consume

    def _consume_chunk(self, chunk, numas_cpus):
        required = chunk['required']
        while required > 0:
            consumed = False
            for rule in chunk['rules']:
                numa_id = self._get_numa_id(rule, numas_cpus)

                length = len(numas_cpus[numa_id])
                consume = self._get_consume_count(rule, length, required)

                if consume == 0:
                    continue

                if length < consume:
                    raise ValueError("Failed to consume CPUs for '{0}':"
                                     " try to consume {1} CPUs from NUMA"
                                     " {2}."
                                     .format(rule['name'], consume, numa_id))

                result = self.result.setdefault(rule['name'], [])
                result.extend(numas_cpus[numa_id][:consume])
                self.cpus.extend(numas_cpus[numa_id][:consume])
                numas_cpus[numa_id] = numas_cpus[numa_id][consume:]

                required -= consume
                rule['allocated'] += consume
                consumed = True

            if not consumed:
                break

        for rule in chunk['rules']:
            if rule.get('allocated', 0) < rule.get('min_cpus', 0):
                raise ValueError(
                    "Failed to consume CPUs for '{0}': at least {1} CPUs are"
                    " required, but {2} CPUs are allocated, try to specify"
                    " more CPUs or change configuration."
                    .format(rule['name'], rule['min_cpus'],
                            rule.get('allocated', 0)))
        return required


def _prepare_dpdk(cpus_consumer, dpdk_info, nics_numas):
    if not dpdk_info or dpdk_info['required_cpus'] == 0:
        return
    if not nics_numas:
        raise ValueError(
            "DPDK CPUs distribution error: there is no"
            " any configured DPDK interface")

    required = dpdk_info['required_cpus']
    # currently there is requirements that ovs_core_mask
    # should contain 1 CPU
    cpus_consumer.add({
        'required': 1,
        'rules': [{
            'name': 'ovs_core_mask',
            'min_cpus': 1,
            'max_cpus': 1,
            'numa_id': nics_numas[0],
        }],
    })
    required -= 1
    chunk = {
        'required': required,
        'rules': []
    }
    for nic_numa in nics_numas:
        chunk['rules'].append({
            'name': 'ovs_pmd_core_mask',
            'min_cpus': 1,
            'max_cpus': settings.DPDK_MAX_CPUS_PER_NIC,
            'numa_id': nic_numa,
        })
    cpus_consumer.add(chunk)


def _prepare_nova(cpus_consumer, nova_info, dpdk_additional, numa_cpus):
    if not nova_info:
        return
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
        dpdk_additional_chunk['rules'].append({
            'name': 'ovs_pmd_core_mask',
            'numa_id': numa_id,
        })

    nova_chunk = {
        'required': nova_info['required_cpus'],
        'rules': [],
    }
    for numa_id in needed_numas:
        nova_chunk['rules'].append({
            'name': nova_info['name'],
            'numa_id': numa_id,
            'take_all': True,
        })

    cpus_consumer.add(dpdk_additional_chunk)
    cpus_consumer.add(nova_chunk)


def _prepare_components(cpus_consumer, components):
    chunk = {
        'required': 0,
        'rules': []
    }
    for component in components.itervalues():
        chunk['required'] += component['required_cpus']
        chunk['rules'].append({
            'name': component['name'],
            'max_cpus': component['required_cpus'],
            'take_all': True,
        })
    cpus_consumer.add(chunk)


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

    cpus_consumer = CPUsConsumer()

    _prepare_dpdk(cpus_consumer, components.pop('dpdk', None), nics_numas)
    dpdk_surplus = cpus_consumer.consume(numa_cpus)

    _prepare_nova(
        cpus_consumer, components.pop('nova', None), dpdk_surplus, numa_cpus)
    _prepare_components(cpus_consumer, components)
    remained = cpus_consumer.consume(numa_cpus)

    if remained != 0:
        raise ValueError(
            "Not all required CPUs were distributed: remained CPUs {0} - {1},"
            " distributed info {2}."
            .format(remained, numa_cpus, cpus_consumer.result))

    return {
        'isolated_cpus': sorted(cpus_consumer.cpus),
        'components': cpus_consumer.result
    }
