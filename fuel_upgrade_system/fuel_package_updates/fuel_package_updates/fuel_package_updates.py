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


from itertools import chain
from copy import deepcopy
import functools
import json
import logging
import os
import subprocess
import sys
import traceback
import urllib2
import yaml

try:
    from collections import OrderedDict
except Exception:
    # python 2.6 or earlier use backport
    from ordereddict import OrderedDict

from keystoneclient import exceptions
from keystoneclient.v2_0 import Client as keystoneclient

from optparse import OptionParser
from urlparse import urlparse

logger = logging.getLogger(__name__)


KEYSTONE_CREDS = {
    'username': os.environ.get('KEYSTONE_USERNAME', 'admin'),
    'password': os.environ.get('KEYSTONE_PASSWORD', 'admin'),
    'tenant_name': os.environ.get('KEYSTONE_TENANT', 'admin'),
}


class Settings(object):
    supported_distros = ('centos', 'ubuntu',)
    supported_releases = ('2014.2-6.1', )
    updates_destinations = {
        'centos': r'/var/www/nailgun/{0}/centos/updates',
        'ubuntu': r'/var/www/nailgun/{0}/ubuntu/updates',
    }
    exclude_dirs = ('repodata/', 'mos?.?/')
    httproot = "/var/www/nailgun"
    port = 8000


class HTTPClient(object):

    def __init__(self, url, keystone_url, credentials, **kwargs):
        logger.debug('Initiate HTTPClient with url %s', url)
        self.url = url
        self.keystone_url = keystone_url
        self.creds = dict(credentials, **kwargs)
        self.keystone = None
        self.opener = urllib2.build_opener(urllib2.HTTPHandler)

    def authenticate(self):
        try:
            logger.debug('Initialize keystoneclient with url %s',
                         self.keystone_url)
            self.keystone = keystoneclient(
                auth_url=self.keystone_url, **self.creds)
            # it depends on keystone version, some versions doing auth
            # explicitly some dont, but we are making it explicitly always
            self.keystone.authenticate()
            logger.debug('Authorization token is successfully updated')
        except exceptions.AuthorizationFailure:
            logger.warning(
                'Cant establish connection to keystone with url %s',
                self.keystone_url)

    @property
    def token(self):
        if self.keystone is not None:
            try:
                return self.keystone.auth_token
            except exceptions.AuthorizationFailure:
                logger.warning(
                    'Cant establish connection to keystone with url %s',
                    self.keystone_url)
            except exceptions.Unauthorized:
                logger.warning("Keystone returned unauthorized error, trying "
                               "to pass authentication.")
                self.authenticate()
                return self.keystone.auth_token
        return None

    def get(self, endpoint):
        req = urllib2.Request(self.url + endpoint)
        return self._open(req)

    def post(self, endpoint, data=None, content_type="application/json"):
        if not data:
            data = {}
        logger.info('self url is %s' % self.url)
        req = urllib2.Request(self.url + endpoint, data=json.dumps(data))
        req.add_header('Content-Type', content_type)
        return self._open(req)

    def put(self, endpoint, data=None, content_type="application/json"):
        if not data:
            data = {}
        req = urllib2.Request(self.url + endpoint, data=json.dumps(data))
        req.add_header('Content-Type', content_type)
        req.get_method = lambda: 'PUT'
        return self._open(req)

    def delete(self, endpoint):
        req = urllib2.Request(self.url + endpoint)
        req.get_method = lambda: 'DELETE'
        return self._open(req)

    def _open(self, req):
        try:
            return self._get_response(req)
        except urllib2.HTTPError as e:
            if e.code == 401:
                logger.warning('Authorization failure: {0}'.format(e.read()))
                self.authenticate()
                return self._get_response(req)
            else:
                raise

    def _get_response(self, req):
        if self.token is not None:
            try:
                logger.debug('Set X-Auth-Token to {0}'.format(self.token))
                req.add_header("X-Auth-Token", self.token)
            except exceptions.AuthorizationFailure:
                logger.warning('Failed with auth in http _get_response')
                logger.warning(traceback.format_exc())
        return self.opener.open(req)


def repo_merge(a, b):
    '''merges two lists of repositories. b replaces records from a.'''
    if not isinstance(b, list):
        return deepcopy(b)

    result = OrderedDict()
    for repo in chain(a, b):
        result[repo['name']] = repo

    return result.values()


class FuelWebClient(object):

    def __init__(self, admin_node_ip):
        self.admin_node_ip = admin_node_ip
        self.client = NailgunClient(admin_node_ip)
        super(FuelWebClient, self).__init__()

    def environment(self):
        """Environment Model
        :rtype: EnvironmentModel
        """
        return self._environment

    def update_cluster_repos(self,
                             cluster_id,
                             settings=None):
        """Updates a cluster with new settings
        :param cluster_id:
        :param settings:
        """

        if settings is None:
            settings = {}

        attributes = self.client.get_cluster_attributes(cluster_id)

        if 'repo_setup' in attributes['editable']:
            repos_attr = attributes['editable']['repo_setup']['repos']
            repos_attr['value'] = repo_merge(repos_attr['value'], settings)

        logger.debug("Try to update cluster "
                     "with next attributes {0}".format(attributes))
        self.client.update_cluster_attributes(cluster_id, attributes)


class NailgunClient(object):

    def __init__(self, admin_node_ip, **kwargs):
        url = "http://{0}:8000".format(admin_node_ip)
        logger.debug('Initiate Nailgun client with url %s', url)
        self.keystone_url = "http://{0}:5000/v2.0".format(admin_node_ip)
        self._client = HTTPClient(url=url, keystone_url=self.keystone_url,
                                  credentials=KEYSTONE_CREDS,
                                  **kwargs)
        super(NailgunClient, self).__init__()

    def json_parse(func):
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            response = func(*args, **kwargs)
            return json.loads(response.read())
        return wrapped

    @property
    def client(self):
        return self._client

    @json_parse
    def get_cluster_attributes(self, cluster_id):
        return self.client.get(
            "/api/clusters/{0}/attributes/".format(cluster_id)
        )

    @json_parse
    def update_cluster_attributes(self, cluster_id, attrs):
        return self.client.put(
            "/api/clusters/{0}/attributes/".format(cluster_id),
            attrs
        )


class UpdatePackagesException(Exception):
    pass


def exec_cmd(cmd):
    logger.debug('Execute command "%s"', cmd)
    child = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True)

    logger.debug('Stdout and stderr of command "%s":', cmd)
    for line in child.stdout:
        logger.debug(line.rstrip())

    return _wait_and_check_exit_code(cmd, child)


def _wait_and_check_exit_code(cmd, child):
    child.wait()
    exit_code = child.returncode
    logger.debug('Command "%s" was executed', cmd)
    return exit_code


def get_ubuntu_repos(repopath, ip, httproot, port, baseurl=None):
    # TODO(mattymo): parse all repo metadata
    repolist = ('mos6.1-updates', 'mos6.1-security', 'mos6.1-holdback')
    if baseurl:
        repourl = "{baseurl}/{repopath}".format(
            baseurl=baseurl,
            repopath=repopath.replace(httproot, ''))
    else:
        repourl = "http://{ip}:{port}/{repopath}".format(
            ip=ip,
            port=port,
            repopath=repopath.replace(httproot, ''))

    repos = []
    for repo in repolist:
        # FIXME(mattymo): repositories cannot have a period in their name
        name = repo.replace('6.1', '')
        repoentry = {
            "type": "deb",
            "name": name,
            "uri": repourl,
            "suite": repo,
            "section": "main restricted",
            "priority": 1050
        }

        if "holdback" in repo:
            repoentry['priority'] = 1100

        repos.append(repoentry)

    return repos


def get_centos_repos(repopath, ip, httproot, port, baseurl=None):
    if baseurl:
        repourl = "{baseurl}/{repopath}".format(
            baseurl=baseurl,
            repopath=repopath.replace(httproot, ''))
    else:
        repourl = "http://{ip}:{port}/{repopath}".format(
            ip=ip,
            port=port,
            repopath=repopath.replace(httproot, ''))

    repoentry = {
        "type": "rpm",
        "name": "MOS-Updates",
        "uri": repourl,
        "priority": 20}
    return [repoentry]


def reindent(s, num_spaces=10):
    return ''.join((num_spaces * ' ') + line for line in s.split('\n'))


def show_env_conf(repos, showuri=False, ip="10.20.0.2"):
    print("Your repositories are now ready for use. You will need to update "
          "your Fuel environment configuration to use these repositories.")
    print("Note: Be sure to replace ONLY the repositories listed below.\n")
    if not showuri:
        print("Replace the entire repos section of your environment using "
              "the following commands:\n  fuel --env 1 env --attributes "
              "--download\n  vim cluster_1/attributes.yaml\n  fuel --env "
              "1 env --attributes --upload")

    if showuri:
        for repo in repos:
            if repo['type'] == "deb":
                print("{name}:\ndeb {uri} {suite} {section}".format(
                      name=repo['name'],
                      uri=repo['uri'],
                      suite=repo['suite'],
                      section=repo['section']))
            else:
                print("{name}:\n{uri}".format(
                      name=repo['name'],
                      uri=repo['uri']))
    else:
        yamldata = {"repos": repos}
        print(reindent(yaml.dump(yamldata, default_flow_style=False)))


def update_env_conf(ip, env_id, distro, repos):
    fwc = FuelWebClient(ip, None)
    fwc.update_cluster_repos(env_id, repos)


def mirror_remote_repository(remote_repo_url, local_repo_path, exclude_dirs,
                             distro):
    repo_url = urlparse(remote_repo_url)
    cut_dirs = len(repo_url.path.strip('/').split('/'))
    if "rsync://" in remote_repo_url:
        excl_dirs = "ubuntu/dists/mos?.?/,repodata/"
        download_cmd = ('rsync --exclude="*.key","*.gpg",{excl_dirs} -vPr '
                        '{url} {path}').format(pwd=repo_url.path.rstrip('/'),
                                               path=local_repo_path,
                                               excl_dirs=excl_dirs,
                                               url=repo_url.geturl())
    else:
        excl_dirs = "--exclude-directories='ubuntu/dists/mos?.?/,repodata'"
        download_cmd = (
            'wget --recursive --no-parent --no-verbose -R "*.html" -R '
            '"*.gif" -R "*.key" -R "*.gpg" -R "*.dsc" -R "*.tar.gz" '
            '{excl_dirs} --directory-prefix {path} -nH '
            '--cut-dirs={cutd} '
            '{url}').format(pwd=repo_url.path.rstrip('/'),
                            excl_dirs=excl_dirs,
                            path=local_repo_path,
                            cutd=cut_dirs,
                            url=repo_url.geturl())

    logger.debug('Execute command "%s"', download_cmd)
    if exec_cmd(download_cmd) != 0:
        raise UpdatePackagesException('Mirroring of remote packages'
                                      ' repository failed!')


def setup_logging():
    sh = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    sh.setFormatter(formatter)
    logger.addHandler(sh)
    logger.setLevel(logging.INFO)


def get_parser():
    parser = OptionParser(
        description="Pull updates for a given release of Fuel based on "
                    "the provided URL."
    )
    parser.add_option('-l', '--list-distros', dest='list_distros',
                      default=None, action="store_true",
                      help='List available distributions.')
    parser.add_option('-d', '--distro', dest='distro', default=None,
                      help='Distribution name (required)')
    parser.add_option('-r', '--release', dest='release', default=None,
                      help='Fuel release name (required)')
    parser.add_option("-u", "--url", dest="url", default="",
                      help="Remote repository URL (required)")
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="Enable debug output")
    parser.add_option("-i", "--show-uris", dest="showuri", default=False,
                      action="store_true",
                      help="Show URIs for new repositories (optional). "
                      "Useful for WebUI.")
    parser.add_option("-a", "--apply", dest="apply", default=False,
                      action="store_true",
                      help="Apply changes to Fuel environment (optional)")
    parser.add_option("-e", "--env", dest="env", default=None,
                      help="Fuel environment ID (required for option -a)")
    parser.add_option("-s", "--fuel-server", dest="ip", default="10.20.0.2",
                      help="Address of Fuel Master public address (defaults "
                      "to 10.20.0.2)")
    parser.add_option("-b", "--baseurl", dest="baseurl", default=None,
                      help="URL prefix for mirror, such as http://myserver."
                      "company.com/repos (optional)")
    parser.add_option("-p", "--password", dest="admin_pass", default=None,
                      help="Fuel Master admin password (defaults to admin)."
                      " Alternatively, use env var KEYSTONE_PASSWORD).")

    return parser


def main():
    setup_logging()
    parser = get_parser()

    (options, args) = parser.parse_args()

    if options.verbose:
        logger.setLevel(logging.DEBUG)

    if options.list_distros:
        logger.info("Available distributions:\n  {0}".format(
            "\n  ".join(Settings.supported_distros)))
        sys.exit(0)

    if options.distro not in Settings.supported_distros:
        raise UpdatePackagesException(
            'Distro "{0}" is not supported. Please specify one of the '
            'following: "{1}". See help (--help) for details.'.format(
                options.distro, ', '.join(Settings.supported_distros)))

    if options.release not in Settings.supported_releases:
        raise UpdatePackagesException(
            'Fuel release "{0}" is not supported. Please specify one of the '
            'following: "{1}". See help (--help) for details.'.format(
                options.release, ', '.join(Settings.supported_releases)))

    if 'http' not in urlparse(options.url) and 'rsync' not in \
            urlparse(options.url):
        raise UpdatePackagesException(
            'Repository url "{0}" does not look like valid URL. '
            'See help (--help) for details.'.format(options.url))

    if options.apply and not options.env:
        raise UpdatePackagesException(
            '--apply option requires --env to be specified. '
            'See help (--help) for details.')

    updates_path = Settings.updates_destinations[options.distro].format(
        options.release)
    if not os.path.exists(updates_path):
        os.makedirs(updates_path)

    logger.info('Started mirroring remote repository...')
    mirror_remote_repository(options.url, updates_path,
                             Settings.exclude_dirs, options.distro)
    logger.info('Remote repository "{url}" for "{release}" ({distro}) was '
                'successfuly mirrored to {path} folder.'.format(
                    url=options.url,
                    release=options.release,
                    distro=options.distro,
                    path=updates_path))
    if options.distro == "ubuntu":
        repos = get_ubuntu_repos(updates_path, options.ip, Settings.httproot,
                                 Settings.port, options.baseurl)
    elif options.distro == "centos":
        repos = get_centos_repos(updates_path, options.ip, Settings.httproot,
                                 Settings.port, options.baseurl)
    else:
        raise UpdatePackagesException('Unknown distro "{0}"'.format(
            options.distro))
    if options.admin_pass:
        KEYSTONE_CREDS['password'] = options.admin_pass
    if options.apply:
        update_env_conf(options.ip, options.env, options.distro, repos)
    else:
        show_env_conf(repos, options.showuri, options.ip)


if __name__ == '__main__':
    main()
