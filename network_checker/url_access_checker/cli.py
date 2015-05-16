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

import os
import sys
# fixed in cmd2 >=0.6.6
os.environ['EDITOR'] = '/usr/bin/nano'

from cliff.commandmanager import CommandManager

from fuel_network_checker import base_app


class UrlAccessCheckApp(base_app.BaseApp):
    LOG_FILENAME = '/var/log/url_access_checker.log'

    def __init__(self):
        super(UrlAccessCheckApp, self).__init__(
            description='Url access check application',
            version='0.1',
            command_manager=CommandManager('urlaccesscheck'),
        )


def main(argv=sys.argv[1:]):
    myapp = UrlAccessCheckApp()
    return myapp.run(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
