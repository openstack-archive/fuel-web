#!/usr/bin/env python

#    Copyright 2016 Mirantis, Inc.
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
from contextlib import contextmanager
from argparse import ArgumentParser
from itertools import groupby

import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(SCRIPT_DIR, 'test_extensions.yaml')) as fp:
    CONFIG = yaml.load(fp)


def parse_arguments(argv):
    parser = ArgumentParser()
    parser.add_argument('git_base_url')
    parser.add_argument('projects', nargs='+')

    args = parser.parse_known_args(argv)[0]
    return args.projects


def run_cloner(argv):
    print '*'*20, "RUN CLONER", '*'*20
    call = '{path} {argv}'.format(
        path=CONFIG['zuul_cloner_bin'],
        argv=' '.join(argv)
    )
    ret = os.system(call)
    if ret != 0:
        raise SystemError('WTF?: {}'.format(call))


@contextmanager
def change_dir(path):
    curdir = os.getcwd()
    os.chdir(path)
    yield
    os.chdir(curdir)


def run_tests(to_test):
    grouped = groupby(map(lambda x: x.split('/'), sorted(to_test)),
                      key=lambda x: x[0])
    for repo, projects in grouped:
        with change_dir(repo):
            for project in projects:
                run_test_command(project[1])


def run_test_command(project):
    print '*'*20, "RUN TESTS for", project, '*'*20
    with change_dir(project):
        os.system(CONFIG['test_cmd'])


def set_nailgun_path(projects):
    # '..' cause we're in 'fuel-web/bin'
    fuelw = next((p for p in projects if p.split('/')[1] == 'fuel-web'), '..')
    os.environ['NAILGUN_PATH'] = os.path.normpath(
        os.path.join(SCRIPT_DIR, fuelw, 'nailgun'))


def main():
    projects = parse_arguments(sys.argv[1:])
    run_cloner(sys.argv[1:])
    set_nailgun_path(projects)
    run_tests(projects)


if __name__ == '__main__':
    main()
