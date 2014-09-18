# Copyright 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
from random import choice
import re
import shlex
import string
import subprocess

LOG = logging.getLogger(__name__)


def genmac(start=None):
    LOG.debug('Generating mac address')
    if start is None:
        start = u'00:16:3e:'
    chars = string.digits + 'abcdef'
    mac = start + u':'.join([
        '{0}{1}'.format(choice(chars), choice(chars)) for _ in xrange(3)])
    LOG.debug('Generated mac: %s' % mac)
    return mac


class ExecResult(object):
    def __init__(self, stdout, stderr='', return_code=0):
        self.stdout = stdout
        self.stderr = stderr
        self.return_code = return_code

    def __str__(self):
        return self.stdout

    def __repr__(self):
        return self.stdout


def execute(command, to_filename=None, cwd=None):
    LOG.debug('Trying to execute command: %s', command)
    commands = [c.strip() for c in re.split(ur'\|', command)]

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
                env=os.environ,
                stdin=(process[-1].stdout if process else None),
                stdout=(to_file
                        if (len(process) == len(commands) - 1) and to_file
                        else subprocess.PIPE),
                stderr=(subprocess.PIPE),
                cwd=cwd
            ))
        except OSError as e:
            return (1, '', '{0}\n'.format(e))

        if len(process) >= 2:
            process[-2].stdout.close()
    stdout, stderr = process[-1].communicate()
    out = ExecResult(stdout, stderr=stderr, return_code=process[-1].returncode)
    return out
