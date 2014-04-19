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
import json

from shotgun.logger import configure_logger
configure_logger()

from shotgun.config import Config
from shotgun.manager import Manager


def parse_args():
    """Parse arguments and return them

    :returns: argparse object
    """
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '-c',
        '--config',
        help='configuration file',
        required=True)

    return parser.parse_args()


def read_config(config_path):
    """Reads config

    :param config_path: path to configuration file
    :returns: dict with configuration data
    """
    with open(config_path, "r") as fo:
        config = json.loads(fo.read())

    return config


def make_snapshot(args):
    """Generates snapshot

    :param args: argparse object
    """
    config_object = Config(read_config(args.config))
    manager = Manager(config_object)
    print(manager.snapshot())


def main():
    """Entry point
    """
    make_snapshot(parse_args())
