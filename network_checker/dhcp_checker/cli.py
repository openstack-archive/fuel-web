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
from logging import handlers
import os
import sys
# fixed in cmd2 >=0.6.6
os.environ['EDITOR'] = '/usr/bin/nano'

from cliff.app import App
from cliff.commandmanager import CommandManager


class DhcpApp(App):
    DEFAULT_VERBOSE_LEVEL = 0

    def __init__(self):
        super(DhcpApp, self).__init__(
            description='Dhcp check application',
            version='0.1',
            command_manager=CommandManager('dhcp.check'),
        )

    def configure_logging(self):
        super(DhcpApp, self).configure_logging()
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s (%(module)s) %(message)s',
            "%Y-%m-%d %H:%M:%S")

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.ERROR)
        stream_handler.setFormatter(formatter)

        file_handler = handlers.TimedRotatingFileHandler(
            '/var/log/dhcp_checker.log')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)

        logger.addHandler(stream_handler)
        logger.addHandler(file_handler)

        # set scapy logger level only to ERROR
        # due to a lot of spam
        runtime_logger = logging.getLogger('scapy.runtime')
        runtime_logger.setLevel(logging.ERROR)


def main(argv=sys.argv[1:]):
    myapp = DhcpApp()
    return myapp.run(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
