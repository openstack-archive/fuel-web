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
import os
import sys
from urlparse import urlparse

from fuel_package_updates.clients import FuelWebClient
from fuel_package_updates.log import setup_logging
from fuel_package_updates import repo_utils
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
                        help='Distribution name (required)')
    parser.add_argument('-r', '--release', dest='release', required=True,
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
                        help="Fuel Master admin password (defaults to admin)."
                        " Alternatively, use env var KEYSTONE_PASSWORD).")

    options = parser.parse_args()
    options.distro = options.distro.lower()

    return options


def check_options(options):
    if options.verbose:
        setup_logging(LOGGER_NAME, logging.DEBUG)
    else:
        setup_logging(LOGGER_NAME)

    if options.list_distros:
        print("Available distributions:\n  {0}".format(
              "\n  ".join(SETTINGS.supported_distros)))
        sys.exit(0)

    if options.distro not in SETTINGS.supported_distros:
        utils.exit_with_error(
            'Distro "{0}" is not supported. Please specify one of the '
            'following: "{1}". See help (--help) for details.'.format(
                options.distro,
                ', '.join(SETTINGS.supported_distros)))

    if options.release not in SETTINGS.supported_releases:
        utils.exit_with_error(
            'Fuel release "{0}" is not supported. Please specify one of the '
            'following: "{1}". See help (--help) for details.'.format(
                options.release,
                ', '.join(SETTINGS.supported_releases)))

    if 'http' not in urlparse(options.url) and \
       'rsync' not in urlparse(options.url):
        utils.exit_with_error(
            'Repository url "{0}" does not look like valid URL. '
            'See help (--help) for details.'.format(options.url))


def perform_actions(options):
    updates_path = SETTINGS.updates_destinations[options.distro].format(
        options.release)
    if not os.path.exists(updates_path):
        os.makedirs(updates_path)

    logger.info('Started mirroring remote repository...')

    repo_utils.mirror_remote_repository(options.distro, options.url,
                                        updates_path)
    logger.info('Remote repository "{url}" for "{release}" ({distro}) was '
                'successfuly mirrored to {path} folder.'.format(
                    url=options.url,
                    release=options.release,
                    distro=options.distro,
                    path=updates_path))

    repos = repo_utils.get_repos(options.distro, updates_path, options.ip,
                                 SETTINGS.port, SETTINGS.httproot,
                                 options.baseurl)

    if options.admin_pass:
        SETTINGS.keystone_creds['password'] = options.admin_pass
    if options.apply:
        fwc = FuelWebClient(options.ip, SETTINGS.port, SETTINGS.keystone_creds)
        fwc.update_cluster_repos(options.apply, repos)
    else:
        repo_utils.show_env_conf(repos, options.ip, options.showuri)


def main():
    options = parse_args()
    check_options(options)
    perform_actions(options)


if __name__ == '__main__':
    main()
