#    Copyright 2013 Mirantis, Inc.
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

import logging
import os
import re
import shlex
import socket
import subprocess


logger = logging.getLogger(__name__)


def hostname():
    return socket.gethostname()


def is_ip(name):
    return (re.search(ur"([0-9]{1,3}\.){3}[0-9]{1,3}", name) and True)


def fqdn(name=None):
    if name:
        return socket.getfqdn(name)
    return socket.getfqdn(socket.gethostname())


def is_local(name):
    if name in ("localhost", hostname(), fqdn()):
        return True
    return False


def execute(command, to_filename=None):
    logger.debug("Trying to execute command: %s", command)
    commands = [c.strip() for c in re.split(ur'\|', command)]
    env = os.environ
    env["PATH"] = "/bin:/usr/bin:/sbin:/usr/sbin"

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
                stderr=(subprocess.PIPE)
            ))
        except OSError as e:
            return (1, "", "{0}\n".format(e))

        if len(process) >= 2:
            process[-2].stdout.close()
    stdout, stderr = process[-1].communicate()
    return (process[-1].returncode, stdout, stderr)


def fabric_monkey_patch():
    """Current Fabric incorrectly checks for a directory, because it uses
    lstat() which returns False in case of symlink to a directory.

    The issue occurs when shotgun wants to download a directory that contains
    a symlink to another directory. For example, we have

        /var/log/remote -> /var/log/docker-logs/remote

    The fix was proposed to fabric master branch:

        https://github.com/fabric/fabric/pull/1147
    """
    from fabric.sftp import SFTP
    import stat

    def isdir(self, path):
        try:
            return stat.S_ISDIR(self.ftp.stat(path).st_mode)
        except IOError:
            return False

    SFTP.isdir = isdir
