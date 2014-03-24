# -*- coding: utf-8 -*-

#    Copyright 2014 Mirantis, Inc.
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
import sys
import traceback

from fuel_update_downloader.downloader import Downloader
from fuel_update_downloader import errors


def handle_exception(exc):
    if isinstance(exc, errors.FuelUpgradeException):
        sys.stderr.write(exc.message + "\n")
        sys.exit(-1)
    else:
        traceback.print_exc(exc)
        sys.exit(-1)


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--src',
        help='update url',
        required=True)
    parser.add_argument(
        '--dst',
        help='update path with update name',
        required=True)
    parser.add_argument(
        '--checksum',
        help='checksum of file',
        required=True)
    parser.add_argument(
        '--size',
        help='required free space for upgrade',
        required=True,
        type=int)

    return parser.parse_args()


def run_upgrade(args):
    """Run upgrade on master node
    """
    downloader = Downloader(
        src_path=args.src,
        dst_path=args.dst,
        checksum=args.checksum,
        required_free_space=args.size)

    downloader.run()


def main():
    """Entry point
    """
    try:
        run_upgrade(parse_args())
    except Exception as exc:
        handle_exception(exc)
