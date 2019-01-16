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
import operator

from nailgun import consts
from nailgun.settings import settings


"""This module is responsible for components CPU distribution

The special logic is applied for Nova and DPDK, due to
particular requirements. These requirements can be described as:

    1. DPDK component CPU pinning has two parts:
        * OVS pmd core CPUs - These CPUs must be placed on the
          NUMAs where DPDK NIC is located. Since DPDK NIC can
          handle about 12 Mpps/s and 1 CPU can handle about
          3 Mpps/s there is no necessity to place more than
          4 CPUs per NIC. Let's name all remained CPUs as
          additional CPUs.
        * OVS Core CPUs - 1 CPU is enough and that CPU should
          be taken from any NUMA where at least 1 OVS pmd core
          CPU is located

    2. To improve Nova and DPDK performance, all additional CPUs
       should be distributed along with Nova's CPUs.

To fulfill these requirements CPUConsumer will be used. Since
requirement may need the results of the previous distribution, CPUConsumer
uses chunks. Thus it's possible to proceed requirements step-by-step.
Chunk contains information about sum of required CPUs and rules.
Rule has properties about particular CPU placement, such as:

    * component_name - what component pinned CPU will belong to
    * numa_id - NUMA where CPU should be pinned
    * max_cpus - Maximum number of CPUs that can be pinned for this rule
    * min_cpus - Minimum number of CPUs that must be pinned for this rule
    * take_all - take all unpinned CPUs from NUMA node

if take_all is not True than CPUs will be pinned one-by-one from specified
NUMA or from NUMA with maximum number of unpinned CPUs.

"""


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
            return max(enumerate(numas_cpus), key=lambda x: len(x[1]))[0]
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
        self.chunks.extend(chunks)

    def consume(self):
        remained = 0
        while self.chunks:
            remained += self._consume_chunk(self.chunks.popleft())
        return remained

    def _consume_rule(self, rule, numa_id, consume):
        result = self.result.setdefault(rule.component_name, [])

        consumed_cpus = self.numas_cpus[numa_id][:consume]
        result.extend(consumed_cpus)
        self.cpus.extend(consumed_cpus)
        self.numas_cpus[numa_id] = self.numas_cpus[numa_id][consume:]
        rule.allocated += consume

    def _consume_chunk(self, chunk):
        remained = chunk['required']
        while remained > 0:
            consumed = False
            for rule in chunk['rules']:
                numa_id = rule.get_numa_id(self.numas_cpus)

                remained_cpus = len(self.numas_cpus[numa_id])
                consume = rule.get_consume_count(remained_cpus, remained)

                if consume == 0:
                    continue

                if remained_cpus < consume:
                    raise ValueError(
                        "Please specify more CPUs."
                        " Failed to consume CPUs for '{0}':"
                        " try to consume {1} CPUs from NUMA {2}."
                        .format(rule.component_name, consume, numa_id))

                self._consume_rule(rule, numa_id, consume)

                remained -= consume
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
        return remained


def _make_dpdk_chunks(dpdk_info, nics_numas):
    """Creates chunks for DPDK

    DPDK required two types of CPUs to be pinned -
    ovs_core_mask and ovs_pmd_core_mask.
    Firstly, if dpdk_info is None or if it doesn't have
    required cpus, we don't care about DPDK CPU distribution
    ovsdpdk will do it by itself.
    Secondly, if there is no DPDK NICs, algorithm doesn't know
    where CPUs should be placed.
    For all other cases algorithm requires at least 1 CPU per DPDK
    NIC for ovs_pmd_core_mask and 1 for ovs_core_mask
    """

    if not dpdk_info or not dpdk_info['required_cpus']:
        return []
    if not nics_numas:
        raise ValueError(
            "DPDK CPUs distribution error: there is no"
            " configured DPDK interfaces.")

    required = dpdk_info['required_cpus']
    # currently there is requirements that ovs_core_mask
    # should contain 1 CPU
    core_chunk = {
        'required': consts.DPDK_OVS_CORE_CPUS,
        'rules': [
            Rule('ovs_core_mask', numa_id=nics_numas[0],
                 min_cpus=1, max_cpus=consts.DPDK_OVS_CORE_CPUS)
        ]
    }

    required -= consts.DPDK_OVS_CORE_CPUS
    threads_chunk = {
        'required': required,
        'rules': [
            Rule('ovs_pmd_core_mask', numa_id=nic_numa, min_cpus=1,
                 max_cpus=settings.DPDK_MAX_CPUS_PER_NIC)
            for nic_numa in nics_numas
        ]
    }

    return [core_chunk, threads_chunk]


def _make_nova_chunks(nova_info, dpdk_additional, numa_cpus):
    """Create chunks for Nova

    The next algorithm sorts NUMAs in descending order by
    CPUs number and calculates the needed amount of
    NUMAs to fit Nova CPUs and additional CPUs
    """

    if not nova_info:
        return [{
            'required': dpdk_additional,
            'rules': [],
        }]
    # sort by number of CPUs per NUMA in descending order
    # the result will be a list of tuple elements
    # (number_of_cpus_per_numa, numa_id)
    sorted_numas = sorted(
        ((len(cpus), i) for i, cpus in enumerate(numa_cpus)),
        key=lambda x: x[0],
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
            "Not enough CPUs for nova and additional DPDK:"
            " total required {0} actual {1}"
            .format(total_required, cpus_number))

    dpdk_additional_chunk = {
        'required': dpdk_additional,
        'rules': [
            Rule('ovs_pmd_core_mask', numa_id=numa_id)
            for numa_id in needed_numas
        ],
    }

    nova_chunk = {
        'required': nova_info['required_cpus'],
        'rules': [
            Rule('nova', numa_id=numa_id, take_all=True)
            for numa_id in needed_numas
        ],
    }

    return [dpdk_additional_chunk, nova_chunk]


def _make_components_chunks(components):
    rules = []
    required = 0

    for component in components.values():
        required += component['required_cpus']
        rules.append(
            Rule(component['name'], max_cpus=component['required_cpus'],
                 take_all=True)
        )

    rules.sort(key=operator.attrgetter('component_name'))
    return [{
        'required': required,
        'rules': rules,
    }]


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
    for numa in sorted(numa_nodes, key=lambda n: n['id']):
        numa_cpus.append(numa['cpus'][:])

    cpus_consumer = CPUsConsumer(numa_cpus)

    cpus_consumer.add(_make_dpdk_chunks(
        components.pop('dpdk', None), nics_numas))
    dpdk_additional = cpus_consumer.consume()

    cpus_consumer.add(_make_nova_chunks(
        components.pop('nova', None), dpdk_additional, numa_cpus))
    cpus_consumer.add(_make_components_chunks(components))
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
