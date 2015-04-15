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

import os

import requests
import six
import yaml

from nailgun.utils import grouper


def get_release_file(repo, retries=1):
    """Get Release content of a given repo.

    :param repo: a repo as dict
    :returns: a release's content as string
    """
    if repo['section']:
        # We can't use urljoin here because it works pretty bad in
        # cases when 'uri' doesn't have a trailing slash.
        download_uri = os.path.join(
            repo['uri'], 'dists', repo['suite'], 'Release')
    else:
        # Well, we have a flat repo case, so we should download Release
        # file from a different place. Please note, we have to strip
        # a leading slash from suite because otherwise the download
        # link will be wrong.
        download_uri = os.path.join(
            repo['uri'], repo['suite'].lstrip('/'), 'Release')

    for _ in six.moves.range(0, retries):
        response = requests.get(download_uri)

        # do not perform retries if release is not found
        if response.status_code == 404:
            break

    response.raise_for_status()
    return response.text


def parse_release_file(content):
    """Parse Debian repo's Release file content.

    :param content: a Debian's Release file content
    :returns: a dict with repo's attributes
    """

    # TODO(ikalnitsky): Consider to use some existing library for
    # parsing debian's release file (e.g. python-debian).

    _multivalued_fields = {
        'SHA1': ['sha1', 'size', 'name'],
        'SHA256': ['sha256', 'size', 'name'],
        'SHA512': ['sha512', 'size', 'name'],
        'MD5Sum': ['md5sum', 'size', 'name'],
    }

    # debian data format is very similiar to yaml, except
    # multivalued field. so we can parse it just like yaml
    # and then perform additional transformation for those
    # fields (we know which ones are multivalues).
    data = yaml.load(content)

    for attr, columns in six.iteritems(_multivalued_fields):
        if attr not in data:
            continue

        values = data[attr].split()
        data[attr] = []

        for group in grouper(values, len(columns)):
            data[attr].append(dict(zip(columns, group)))

    return data


def get_apt_preferences_line(deb_release):
    """Get an APT Preferences line from repo's release information.

    :param deb_release: a Debian's Release content as dict
    :returns: an apt pinning line as string
    """
    _transformations = {
        'Archive': 'a',
        'Suite': 'a',       # suite is a synonym for archive
        'Codename': 'n',
        'Version': 'v',
        'Origin': 'o',
        'Label': 'l',
    }

    conditions = set()
    for field, condition in six.iteritems(_transformations):
        if field in deb_release:
            conditions.add('{0}={1}'.format(condition, deb_release[field]))

    return ','.join(conditions)
