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

from cliff import command

import url_access_checker.api as api
import url_access_checker.errors as errors
from url_access_checker.network import manage_network


LOG = logging.getLogger(__name__)


class CheckUrls(command.Command):
    """Check if it is possible to retrieve urls."""
    def get_parser(self, prog_name):
        parser = super(CheckUrls, self).get_parser(prog_name)
        parser.add_argument('urls', type=str, nargs='+',
                            help='List of urls to check')
        return parser

    def take_action(self, parsed_args):
        LOG.info('Starting url access check for {0}'.format(parsed_args.urls))
        try:
            api.check_urls(parsed_args.urls)
        except errors.UrlNotAvailable as e:
            sys.stdout.write(str(e))
            raise e


class CheckUrlsWithSetup(CheckUrls):

    def get_parser(self, prog_name):
        parser = super(CheckUrlsWithSetup, self).get_parser(
            prog_name)
        parser.add_argument('-i', type=str, help='Interface', required=True)
        parser.add_argument('-a', type=str, help='Addr/Mask pair',
                            required=True)
        parser.add_argument('-g', type=str, required=True,
                            help='Gateway to be used as default')
        parser.add_argument('--vlan', type=int, help='Vlan tag')
        return parser

    def take_action(self, pa):
        with manage_network(pa.i, pa.a, pa.g, pa.vlan):
            return super(
                CheckUrlsWithSetup, self).take_action(pa)
