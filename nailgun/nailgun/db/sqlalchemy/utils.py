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


def make_dsn(engine, host, port, user, passwd, name):
    """Constructs DSN string that can be used to connect to database.

    If host starts with '/' it will be treated as a socket and port will be
    ingored.

    :param engine: DB engine
    :param host: DB host or socket
    :param port: DB port (empty if using socket)
    :param user: DB user name
    :param passwd: DB user password
    :param name: name of the database
    """
    if host.startswith('/'):
        # use socket
        dsn = "{engine}://{user}:{passwd}@/{name}?host={host}"
    else:
        # use regular connection
        dsn = "{engine}://{user}:{passwd}@{host}:{port}/{name}"

    return dsn.format(
        engine=engine,
        host=host,
        port=port,
        user=user,
        passwd=passwd,
        name=name,
    )


def fuel_version(release_version):
    """Returns fuel version based on release version.

    A release version consists of 'OSt' and 'MOS' versions:
        '2014.1.1-5.0.2'

    so we need to extract 'MOS' version and returns it as result.

    :returns: an environment version
    """
    # unfortunately, Fuel 5.0 didn't have an env version in release_version
    # so we need to handle that special case
    if release_version == '2014.1':
        version = '5.0'
    else:
        try:
            version = release_version.split('-')[1]
        except IndexError:
            version = ''

    return version


def openstack_version(release_version):
    return release_version.split('-')[0]
