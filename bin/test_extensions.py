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
from contextlib import contextmanager


CONFIG = {
    'git_base': 'git://github.com',
    'zuul-cloner': 'zuul-cloner',
    'projects': [
        {
            'name': 'gitfred/fuel-web',
            'branch': None,
        },
    ],
    'extensions': [
        {
            'name': 'gitfred/bareon-fuel-extension',
            'branch': None,
        },
    ],
}


def build_projects_parameters():
    st = ''
    for project in CONFIG['projects'] + CONFIG['extensions']:
        st += ' {}'.format(project['name'])
        if project['branch']:
            st += ' --project-branch {}={}'.format(project['name'],
                                                   project['branch'])

    return st


def run_cloner():
    projects = build_projects_parameters()
    call = '{path} {git_base} {projects}'.format(
        path=CONFIG['zuul-cloner'],
        git_base=CONFIG['git_base'],
        projects=projects
    )
    ret = os.system(call)
    if ret != 0:
        raise SystemError('WTF?: {}'.format(call))


@contextmanager
def change_dir(path):
    curdir = os.getcwd()
    os.chdir(path)
    yield path
    os.chdir(curdir)


def install_extensions():
    for ext in CONFIG['extensions']:
        directory, name = ext['name'].split('/')
        call = 'pip install -e {}'.format(name)

        with change_dir(directory):
            os.system(call)


if __name__ == '__main__':
    run_cloner()
    install_extensions()
