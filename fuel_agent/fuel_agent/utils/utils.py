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
import os
import re
import shlex
import subprocess

import jinja2
import stevedore.driver

from fuel_agent import errors
from fuel_agent.openstack.common import log as logging


LOG = logging.getLogger(__name__)


#NOTE(agordeev): signature compatible with execute from oslo
def execute(*cmd, **kwargs):
    command = ' '.join(cmd)
    LOG.debug('Trying to execute command: %s', command)
    commands = [c.strip() for c in re.split(ur'\|', command)]
    env = os.environ
    env['PATH'] = '/bin:/usr/bin:/sbin:/usr/sbin'
    check_exit_code = kwargs.pop('check_exit_code', [0])
    ignore_exit_code = False
    to_filename = kwargs.get('to_filename')
    cwd = kwargs.get('cwd')

    if isinstance(check_exit_code, bool):
        ignore_exit_code = not check_exit_code
        check_exit_code = [0]
    elif isinstance(check_exit_code, int):
        check_exit_code = [check_exit_code]

    to_file = None
    if to_filename:
        to_file = open(to_filename, 'wb')

    process = []
    for c in commands:
        try:
            # NOTE(eli): Python's shlex implementation doesn't like unicode.
            # We have to convert to ascii before shlex'ing the command.
            # http://bugs.python.org/issue6988
            encoded_command = c.encode('ascii')

            process.append(subprocess.Popen(
                shlex.split(encoded_command),
                env=env,
                stdin=(process[-1].stdout if process else None),
                stdout=(to_file
                        if (len(process) == len(commands) - 1) and to_file
                        else subprocess.PIPE),
                stderr=(subprocess.PIPE),
                cwd=cwd
            ))
        except OSError as e:
            raise errors.ProcessExecutionError(exit_code=1, stdout='',
                                               stderr=e, cmd=command)
        if len(process) >= 2:
            process[-2].stdout.close()
    stdout, stderr = process[-1].communicate()
    if not ignore_exit_code and process[-1].returncode not in check_exit_code:
        raise errors.ProcessExecutionError(exit_code=process[-1].returncode,
                                           stdout=stdout,
                                           stderr=stderr,
                                           cmd=command)
    return (stdout, stderr)


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


def render_and_save(tmpl_dir, tmpl_names, tmpl_data, file_name):
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(tmpl_dir))
    template = env.get_or_select_template(tmpl_names)
    output = template.render(tmpl_data)
    try:
        with open(file_name, 'w') as f:
            f.write(output)
    except Exception:
        raise errors.TemplateWriteError(
            'Something goes wrong while trying to save'
            'templated data to {0}'.format(file_name))
