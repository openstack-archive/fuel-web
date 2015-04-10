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

from copy import deepcopy
from itertools import chain
import logging
from urlparse import urlparse
import yaml

try:
    from collections import OrderedDict
except Exception:
    # python 2.6 or earlier use backport
    from ordereddict import OrderedDict

from fuel_package_updates.settings import SETTINGS
from fuel_package_updates import utils

logger = logging.getLogger(__name__)


def repo_merge(a, b):
    """merges two lists of repositories. b replaces records from a."""
    if not isinstance(b, list):
        return deepcopy(b)

    result = OrderedDict()
    for repo in chain(a, b):
        result[repo['name']] = repo

    return result.values()


def get_repos(distro, repopath, ip, port, httproot, baseurl=None):
    if baseurl:
        repourl = "{baseurl}/{repopath}".format(
            baseurl=baseurl,
            repopath=repopath.replace("{}/".format(httproot), ''))
    else:
        repourl = "http://{ip}:{port}/{repopath}".format(
            ip=ip,
            port=port,
            repopath=repopath.replace("{}/".format(httproot), ''))

    if distro == 'ubuntu':
        return _get_ubuntu_repos(repourl)
    elif distro == 'centos':
        return _get_centos_repos(repourl)


def _get_ubuntu_repos(repourl):
    ret = []
    for repo in SETTINGS.ubuntu_repos:
        name = repo.replace('6.1', '')
        repoentry = {
            "type": "deb",
            "name": name,
            "uri": repourl,
            "suite": repo,
            "section": "main restricted",
            "priority": 1050}

        if "holdback" in repo:
            repoentry['priority'] = 1100

        ret.append(repoentry)

    return ret


def _get_centos_repos(repourl):
    ret = []
    for repo in SETTINGS.centos_repos:
        repoentry = {
            "type": "rpm",
            "name": repo,
            "uri": repourl,
            "priority": 20}

        ret.append(repoentry)

    return ret


def show_env_conf(repos, ip="10.20.0.2", showuri=False):
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
        spaces = 10
        yamldata = {"repos": repos}
        print(utils.reindent(
            yaml.dump(yamldata, default_flow_style=False), spaces))


def mirror_remote_repository(distro, remote_repo_url, local_repo_path):
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
    if utils.exec_cmd(download_cmd) != 0:
        utils.exit_with_error(
            'Mirroring of remote packages repository failed!')
