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
from fuel_package_updates import settings
from fuel_package_updates import utils

logger = logging.getLogger(settings.LOGGER_NAME)


def get_parser():
    parser = argparse.ArgumentParser(
        description="Pull updates for given release of Fuel - based on "
                    "provided URL. To set more options, provide path "
                    "to custom settings yaml file by setting {var} env "
                    "variable.".format(var=settings.FUEL_SETTINGS_VAR)
    )
    subparsers = parser.add_subparsers()
    set_info_parser(subparsers)
    set_update_parser(subparsers)

    return parser


def set_info_parser(subparsers):
    info_parser = subparsers.add_parser('info',
                                        help='List available distros or '
                                             'print out default settings file '
                                             '(YAML)')
    info_actions = info_parser.add_mutually_exclusive_group()
    info_actions.add_argument('--show-default-settings', action='store_true',
                              dest='show_default_settings',
                              help='Prints out default settings file (YAML).')
    info_actions.add_argument('-l', '--list-distros', dest='list_distros',
                              default=None, action="store_true",
                              help='List available distributions.')
    info_parser.set_defaults(func=check_info_args)


def set_update_parser(subparsers):
    update_parser = subparsers.add_parser('update', help="Perform updates")
    update_parser.add_argument('-d', '--distro', dest='distro',
                               required=True,
                               choices=RepoManager.supported_distros,
                               help='Distribution name (required)')
    update_parser.add_argument('-r', '--release', dest='release',
                               required=True,
                               help='Fuel release name (required)')
    update_parser.add_argument("-u", "--url", dest="url",
                               required=True,
                               help="Remote repository URL (required)")
    update_parser.add_argument("-v", "--verbose",
                               action="store_true", dest="verbose",
                               default=False,
                               help="Enable debug output")
    update_parser.add_argument("-i", "--show-uris", dest="showuri",
                               default=False,
                               action="store_true",
                               help="Show URIs for new repositories (optional)"
                               ". Useful for WebUI.")
    update_parser.add_argument("-a", "--apply", dest="apply",
                               help="Apply changes to Fuel environment with "
                               "given environment ID (optional)")
    update_parser.add_argument("-s", "--fuel-server", dest="ip",
                               default="10.20.0.2",
                               help="Address of Fuel Master public address "
                                    "(defaults to 10.20.0.2)")
    update_parser.add_argument("-b", "--baseurl", dest="baseurl", default=None,
                               help="URL prefix for mirror, such as "
                                    "http://myserver.company.com/repos")
    update_parser.add_argument("-p", "--password", dest="admin_pass",
                               default=None,
                               help="Fuel Master admin password "
                                    "(defaults to admin).")
    update_parser.add_argument("-N", "--no-download",
                               action="store_true",
                               dest="no_download",
                               default=False,
                               help="Skip downloading repository "
                                    "(conflicts with --url)")
    update_parser.add_argument("-m", "--make-default", dest="make_default",
                               default=False, action="store_true",
                               help="Make default for new environments "
                                    "(optional).")
    update_parser.add_argument('-c', '--clear-upstream-repos',
                               action="store_true",
                               dest='clear_upstream_repos',
                               help="Clears upstream repos if {0} distro is "
                                    "chosen. By default just replacing "
                                    "their's URIs".format('ubuntu-baseos'))

    update_parser.set_defaults(func=check_update_args)


def check_update_args(args):
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    if 'http' not in urlparse(args.url) and \
       'rsync' not in urlparse(args.url):
        utils.exit_with_error(
            'Repository url "{0}" does not look like valid URL. '
            'See help (--help) for details.'.format(args.url))

    repo_manager = RepoManager(args)
    repo_manager.perform_actions()


def check_info_args(args):
    if args.list_distros:
        print("Available distributions:\n  {0}".format(
              "\n  ".join(RepoManager.supported_distros)))
    elif args.show_default_settings:
        print("Default settings (YAML):\n")
        with open(settings.DEFAULT_SETTINGS_PATH) as fd:
            print(fd.read())
    else:
        parse_args([sys.argv[1], '--help'])

    sys.exit(0)


def parse_args(args=None):
    parser = get_parser()
    options = parser.parse_args(args=args)
    options.func(options)
    return options


def main(args=None):
    setup_logging(settings.LOGGER_NAME)
    parse_args(args)

if __name__ == '__main__':
    main()
