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

import logging
import sys

from cliff.app import App
from cliff.commandmanager import CommandManager


class UrlAccessCheckApp(App):
    DEFAULT_VERBOSE_LEVEL = 0

    def __init__(self):
        super(UrlAccessCheckApp, self).__init__(
            description='Url access check application',
            version='0.1',
            command_manager=CommandManager('urlaccesscheck'),
        )

    def configure_logging(self):
        super(UrlAccessCheckApp, self).configure_logging()
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s (%(module)s) %(message)s',
            "%Y-%m-%d %H:%M:%S")

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.ERROR)
        stream_handler.setFormatter(formatter)

        file_handler = logging.handlers.TimedRotatingFileHandler(
            '/var/log/url_access_checker.log')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)

        logger.addHandler(stream_handler)
        logger.addHandler(file_handler)


def main(argv=sys.argv[1:]):
    myapp = UrlAccessCheckApp()
    return myapp.run(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
