# -*- coding: utf-8 -*-

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


def extract_fuel_version(release_version):
    """Returns Fuel version based on release version.

    A release version consists of 'OSt' and 'Fuel' versions:
        '2014.1.1-5.0.2'

    so we need to extract 'Fuel' version and returns it as result.

    :returns: a Fuel version
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
