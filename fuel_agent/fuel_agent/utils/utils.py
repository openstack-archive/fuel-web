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

import jinja2
import stevedore.driver

from fuel_agent import errors
from fuel_agent.openstack.common import gettextutils as gtu
from fuel_agent.openstack.common import log as logging
from fuel_agent.openstack.common import processutils


LOG = logging.getLogger(__name__)


def execute(*cmd, **kwargs):
    """Convenience wrapper around oslo's execute() method."""
    LOG.debug(gtu._('Trying to execute command: "%s"'), ' '.join(cmd))
    result = processutils.execute(*cmd, **kwargs)
    LOG.debug(gtu._('Execution completed: "%s"'),
              ' '.join(cmd))
    LOG.debug(gtu._('Command stdout: "%s"') % result[0])
    LOG.debug(gtu._('Command stderr: "%s"') % result[1])
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


def get_driver(name):
    return stevedore.driver.DriverManager(
        namespace='fuel_agent.drivers', name=name).driver


def render_and_save(tmpl_dir, tmpl_name, tmpl_data, file_name):
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(tmpl_dir))
    template = env.get_template(tmpl_name)
    output = template.render(tmpl_data)
    try:
        with open(file_name, 'w') as f:
            f.write(output)
    except Exception:
        raise errors.TemplateWriteError(
            'Something goes wrong while trying to save'
            'templated data to {0}'.format(file_name))
