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

import hashlib
import locale
import math
import os
import re
import shlex
import subprocess
import time

import jinja2
from oslo.config import cfg
import requests
import stevedore.driver
import urllib3

from fuel_agent import errors
from fuel_agent.openstack.common import log as logging


LOG = logging.getLogger(__name__)

u_opts = [
    cfg.IntOpt(
        'http_max_retries',
        default=30,
        help='Maximum retries count for http requests. 0 means infinite',
    ),
    cfg.FloatOpt(
        'http_request_timeout',
        # Setting it to 10 secs will allow fuel-agent to overcome the momentary
        # peak loads when network bandwidth becomes as low as 0.1MiB/s, thus
        # preventing of wasting too much retries on such false positives.
        default=10.0,
        help='Http request timeout in seconds',
    ),
    cfg.FloatOpt(
        'http_retry_delay',
        default=2.0,
        help='Delay in seconds before the next http request retry',
    ),
    cfg.IntOpt(
        'read_chunk_size',
        default=1048576,
        help='Block size of data to read for calculating checksum',
    ),
]

CONF = cfg.CONF
CONF.register_opts(u_opts)


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
    LOG.debug('Trying to get driver: fuel_agent.drivers.%s', name)
    driver = stevedore.driver.DriverManager(
        namespace='fuel_agent.drivers', name=name).driver
    LOG.debug('Found driver: %s', driver.__name__)
    return driver


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


def calculate_md5(filename, size):
    hash = hashlib.md5()
    processed = 0
    with open(filename, "rb") as f:
        while processed < size:
            block = f.read(CONF.read_chunk_size)
            if block:
                block_len = len(block)
                if processed + block_len < size:
                    hash.update(block)
                    processed += block_len
                else:
                    hash.update(block[:size - processed])
                    break
            else:
                break
    return hash.hexdigest()


def init_http_request(url, byte_range=0):
    LOG.debug('Trying to initialize http request object %s, byte range: %s'
              % (url, byte_range))
    retry = 0
    while True:
        if (CONF.http_max_retries == 0) or retry <= CONF.http_max_retries:
            try:
                response_obj = requests.get(
                    url, stream=True,
                    timeout=CONF.http_request_timeout,
                    headers={'Range': 'bytes=%s-' % byte_range})
            except (urllib3.exceptions.DecodeError,
                    urllib3.exceptions.ProxyError,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    requests.exceptions.TooManyRedirects) as e:
                LOG.debug('Got non-critical error when accessing to %s '
                          'on %s attempt: %s' % (url, retry + 1, e))
            else:
                LOG.debug('Successful http request to %s on %s retry' %
                          (url, retry + 1))
                break
            retry += 1
            time.sleep(CONF.http_retry_delay)
        else:
            raise errors.HttpUrlConnectionError(
                'Exceeded maximum http request retries for %s' % url)
    response_obj.raise_for_status()
    return response_obj


def makedirs_if_not_exists(path, mode=0o755):
    """Create directory if it does not exist
    :param path: Directory path
    :param mode: Directory mode (Default: 0o755)
    """
    if not os.path.isdir(path):
        os.makedirs(path, mode=mode)
