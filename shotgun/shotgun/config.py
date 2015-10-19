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
import time

import fabric.api

from shotgun import settings


logger = logging.getLogger(__name__)


class Config(object):
    def __init__(self, data=None):
        self.data = data
        self.time = time.localtime()

    def _timestamp(self, name):
        return "{0}-{1}".format(
            name,
            time.strftime('%Y-%m-%d_%H-%M-%S', self.time)
        )

    @property
    def target(self):
        target = self.data.get("target", settings.TARGET)
        if self.data.get("timestamp", settings.TIMESTAMP):
            target = self._timestamp(target)
        return target

    @property
    def compression_level(self):
        level = self.data.get("compression_level")
        if level is None:
            logger.info(
                'Compression level is not specified,'
                ' Default %s will be used', settings.COMPRESSION_LEVEL)

        level = settings.COMPRESSION_LEVEL

        return '-{level}'.format(level=level)

    @property
    def lastdump(self):
        return self.data.get("lastdump", settings.LASTDUMP)

    def _check_hosts(self):
        offline_hosts = []
        online_hosts = []
        for role, properties in self.data["dump"].iteritems():
            for host in properties.get("hosts", []):
                address = host.get("address", "localhost")
                ssh_key = host.get("ssh-key")
                if address in offline_hosts or address in online_hosts:
                    continue
                with fabric.api.settings(
                    host_string=address,
                    key_filename=ssh_key,
                    timeout=2,
                    command_timeout=3,
                    warn_only=True,
                    abort_on_prompts=True,
                ):
                    logger.debug("Checking whether the host %s is online",
                                 address)
                    try:
                        fabric.api.run('uname -a')
                        logger.debug("Host %s is online", address)
                        online_hosts.append(address)
                    except Exception as e:
                        logger.debug("Host %s is offline/unreachable: %s",
                                     address, str(e))
                        offline_hosts.append(address)
        return online_hosts

    @property
    def objects(self):
        online_hosts = self._check_hosts()
        for role, properties in self.data["dump"].iteritems():
            for host in properties.get("hosts", []):
                for object_ in properties.get("objects", []):
                    object_["host"] = host
                    if host.get("address", "localhost") not in online_hosts:
                        object_["type"] = 'offline'
                    yield object_

    @property
    def timeout(self):
        """Timeout for executing commands."""
        return self.data.get("timeout", settings.DEFAULT_TIMEOUT)
