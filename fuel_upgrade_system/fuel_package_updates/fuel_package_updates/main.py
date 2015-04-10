#!/usr/bin/env python
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

import argparse
import logging
import sys
from urlparse import urlparse

from fuel_package_updates.log import setup_logging
from fuel_package_updates.repo import RepoManager
from fuel_package_updates.settings import SETTINGS
from fuel_package_updates import utils

LOGGER_NAME = 'fuel_package_updates'
logger = logging.getLogger(LOGGER_NAME)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Pull updates for a given release of Fuel based on "
                    "the provided URL."
    )
    parser.add_argument('-l', '--list-distros', dest='list_distros',
                        default=None, action="store_true",
                        help='List available distributions.')
    parser.add_argument('-d', '--distro', dest='distro', required=True,
                        choices=RepoManager.supported_distros,
                        help='Distribution name (required)')
    parser.add_argument('-r', '--release', dest='release', required=True,
                        choices=SETTINGS.supported_releases,
                        help='Fuel release name (required)')
    parser.add_argument("-u", "--url", dest="url", required=True,
                        help="Remote repository URL (required)")
    parser.add_argument("-v", "--verbose",
                        action="store_true", dest="verbose", default=False,
                        help="Enable debug output")
    parser.add_argument("-i", "--show-uris", dest="showuri", default=False,
                        action="store_true",
                        help="Show URIs for new repositories (optional). "
                        "Useful for WebUI.")
    parser.add_argument("-a", "--apply", dest="apply",
                        help="Apply changes to Fuel environment with "
                        "given environment ID (optional)")
    parser.add_argument("-s", "--fuel-server", dest="ip", default="10.20.0.2",
                        help="Address of Fuel Master public address (defaults "
                        "to 10.20.0.2)")
    parser.add_argument("-b", "--baseurl", dest="baseurl", default=None,
                        help="URL prefix for mirror, such as http://myserver."
                        "company.com/repos (optional)")
    parser.add_argument("-p", "--password", dest="admin_pass", default=None,
                        help="Fuel Master admin password (defaults to admin).")

    options = parser.parse_args()
    options.distro = options.distro.lower()

    return options


def check_options(options):
    log_level = logging.INFO
    if options.verbose:
        log_level = logging.DEBUG

    setup_logging(LOGGER_NAME, log_level)

    if options.list_distros:
        print("Available distributions:\n  {0}".format(
              "\n  ".join(RepoManager.supported_distros)))
        sys.exit(0)

    if 'http' not in urlparse(options.url) and \
       'rsync' not in urlparse(options.url):
        utils.exit_with_error(
            'Repository url "{0}" does not look like valid URL. '
            'See help (--help) for details.'.format(options.url))


def main():
    options = parse_args()
    check_options(options)
    repo_manager = RepoManager(options)
    repo_manager.perform_actions()


if __name__ == '__main__':
    main()
