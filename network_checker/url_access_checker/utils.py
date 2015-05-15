#    Copyright 2015 Mirantis, Inc.
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

from logging import getLogger
import subprocess

logger = getLogger(__name__)


def execute(cmd):
    logger.debug('Executing command %s', cmd)
    command = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = command.communicate()
    msg = 'Command {0} executed. RC {1}, stdout {2}, stderr {3}'.format(
        cmd, command.returncode, stdout, stderr)
    if command.returncode:
        logger.error(msg)
    else:
        logger.debug(msg)
    return command.returncode, stdout, stderr
