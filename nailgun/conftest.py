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

import os

from nailgun.settings import settings


def pytest_configure(config):
    if hasattr(config, 'slaveinput'):
        slaveid = config.slaveinput['slaveid']
        db_name = '{0}_{1}'.format(settings.DATABASE['name'], slaveid)
        os.environ['PGUSER'] = settings.DATABASE['user']
        os.environ['PGHOST'] = settings.DATABASE['host']
        os.environ['PGPASSWORD'] = settings.DATABASE['passwd']
        if not_present(db_name):
            os.system("psql -c 'create database {0}'".format(db_name))
        settings.DATABASE['name'] = db_name


def not_present(name):
    return os.system("psql -l | grep -o '^ {0}'".format(name))
