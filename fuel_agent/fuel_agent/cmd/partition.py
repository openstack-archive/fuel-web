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

import sys

from oslo.config import cfg

from fuel_agent.openstack.common import log
from fuel_agent import partition
from fuel_agent import version


def run():
    cfg.CONF(sys.argv[1:], project='fuel-agent',
             version=version.version_info.release_string())
    log.setup('fuel-agent')
    pmanager = partition.PartitionManager()
    pmanager.eval()
