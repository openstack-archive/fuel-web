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

import locale
import math

from fuel_agent.openstack.common import gettextutils as gtu
from fuel_agent.openstack.common import log as logging
from fuel_agent.openstack.common import processutils


LOG = logging.getLogger(__name__)


def execute(*cmd, **kwargs):
    """Convenience wrapper around oslo's execute() method."""
    result = processutils.execute(*cmd, **kwargs)
    LOG.debug(gtu._('Execution completed, command line is "%s"'),
              ' '.join(cmd))
    LOG.debug(gtu._('Command stdout is: "%s"') % result[0])
    LOG.debug(gtu._('Command stderr is: "%s"') % result[1])
    return result


def parse_unit(s, unit, ceil=True):
    """Converts '123.1unit' string into 124 if ceil is True
    and converts '123.9unit' into 123 if ceil is False.
    """

    flt = locale.atof(s.split(unit)[0])
    if ceil:
        return int(math.ceil(flt))
    return int(math.floor(flt))


def B2MiB(b, ceil=True):
    if ceil:
        return int(math.ceil(float(b) / 1024 / 1024))
    return int(math.floor(float(b) / 1024 / 1024))

