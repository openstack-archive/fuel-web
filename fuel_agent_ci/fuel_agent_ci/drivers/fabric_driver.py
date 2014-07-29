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
import sys
import tempfile

from fabric import api as fab

LOG = logging.getLogger(__name__)


def ssh_status(ssh):
    LOG.debug('Trying to get ssh status')
    with fab.settings(
            host_string=ssh.host,
            user=ssh.user,
            key_filename=os.path.join(ssh.env.envdir, ssh.key_filename),
            timeout=ssh.timeout):
        try:
            with fab.hide('running', 'stdout', 'stderr'):
                fab.run('echo')
            LOG.debug('Ssh connection is available')
            return True
        except SystemExit:
            sys.exit()
        except Exception:
            LOG.debug('Ssh connection is not available')
            return False


def ssh_put_content(ssh, file_content, remote_filename):
    LOG.debug('Trying to put content into remote file: %s' % remote_filename)
    with fab.settings(
            host_string=ssh.host,
            user=ssh.user,
            key_filename=os.path.join(ssh.env.envdir, ssh.key_filename),
            timeout=ssh.timeout):
        with tempfile.NamedTemporaryFile() as f:
            f.write(file_content)
            try:
                fab.put(f.file, remote_filename)
            except SystemExit:
                sys.exit()
            except Exception:
                LOG.error('Error while putting content into '
                          'remote file: %s' % remote_filename)
                raise


def ssh_put_file(ssh, filename, remote_filename):
    LOG.debug('Trying to put file on remote host: '
              'local=%s remote=%s' % (filename, remote_filename))
    with fab.settings(
            host_string=ssh.host,
            user=ssh.user,
            key_filename=os.path.join(ssh.env.envdir, ssh.key_filename),
            timeout=ssh.timeout):
        try:
            fab.put(filename, remote_filename)
        except SystemExit:
            sys.exit()
        except Exception:
            LOG.error('Error while putting file on remote host: '
                      'local=%s remote=%s' % (filename, remote_filename))
            raise


def ssh_run(ssh, command, command_timeout=10):
    LOG.debug('Trying to run command on remote host: %s' % command)
    with fab.settings(
            host_string=ssh.host,
            user=ssh.user,
            key_filename=os.path.join(ssh.env.envdir, ssh.key_filename),
            timeout=ssh.timeout,
            command_timeout=command_timeout,
            warn_only=True):
        try:
            with fab.hide('running', 'stdout', 'stderr'):
                return fab.run(command, pty=True)
        except SystemExit:
            sys.exit()
        except Exception:
            LOG.error('Error while putting file on remote host: '
                      '%s' % command)
            raise
