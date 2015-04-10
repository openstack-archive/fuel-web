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

import logging
import os
import yaml

from fuel_package_updates.clients import FuelWebClient
from fuel_package_updates.settings import SETTINGS
from fuel_package_updates import utils

logger = logging.getLogger(__name__)


class RepoManager(object):
    """Class responsible for all repo manipulations.

    supported_distros - add here new distro type once the
                        implementation has been done, otherwise
                        _check_implemented will raise NotImplementedError.
    """
    supported_distros = {
        'ubuntu': 'ubuntu',
        'centos': 'centos',
        'ubuntu-baseos': 'ubuntu_baseos',
    }

    def __init__(self, options):
        self._check_implemented(options.distro)

        # nailgun settings
        self.nailgun_ip = options.ip
        self.nailgun_port = SETTINGS.port
        self.keystone_creds = SETTINGS.keystone_creds
        if options.admin_pass:
            self.keystone_creds['password'] = options.admin_pass

        # package updates options
        self.apply = options.apply
        self.baseurl = options.baseurl
        self.distro = self.supported_distros[options.distro]
        self.release = options.release
        self.repo_url = options.url
        self.showuri = options.showuri
        self.repopath = SETTINGS.updates_destinations[self.distro].format(
            self.release)
        self.updates_path = os.path.join(SETTINGS.httproot, self.repopath)

        if not os.path.exists(self.updates_path):
            try:
                os.makedirs(self.updates_path)
            except OSError:
                utils.exit_with_error(
                    "Unable to create directory for updates in {0}. Please "
                    "make sure you run the script on Fuel Master".format(
                        self.updates_path))

        # other
        self.no_download = options.no_download
        self.make_default = options.make_default
        self.clear_upstream_repos = options.clear_upstream_repos

    def perform_actions(self):
        if not self.no_download:
            self.mirror_remote_repository()
        else:
            logger.info('Skipping repository download...')

        if any([self.apply, self.make_default]):
            fwc = FuelWebClient(self.nailgun_ip, self.nailgun_port,
                                self.keystone_creds)
            if self.apply:
                fwc.update_cluster_repos(self.apply, self.repos)
                logger.info(
                    "Cluster repositories have been successfully updated")

            if self.make_default:
                release_id = fwc.get_release_id(self.distro, self.release)
                if release_id is None:
                    releases = [rel['version'] for rel
                                in fwc.get_available_releases(self.distro)]
                    utils.exit_with_error(
                        "Release not found for {0} - {1}. Available releases: "
                        "{2}".format(
                            self.distro,
                            self.release,
                            ' '.join(releases)))

                fwc.update_default_repos(release_id, self.repos)
                logger.info(
                    "Release repositories have been successfully updated")
        else:
            print(self.show_env_conf())

    def _check_implemented(self, distro):
        if distro not in self.supported_distros:
            raise NotImplementedError(
                "{0} distro is not supported".format(distro))
        return True

    @property
    def repourl(self):
        if not hasattr(self, '_repourl'):
            if self.baseurl:
                self._repourl = "{baseurl}/{repopath}".format(
                    baseurl=self.baseurl.rstrip('/'),
                    repopath=self.repopath)
            else:
                self._repourl = "http://{ip}:{port}/{repopath}".format(
                    ip=self.nailgun_ip,
                    port=self.nailgun_port,
                    repopath=self.repopath)

        return self._repourl

    @property
    def repos(self):
        if not hasattr(self, '_repos_list'):
            self._repos_list = getattr(
                self, "_get_{0}_repos".format(self.distro))()

        return self._repos_list

    def _get_ubuntu_baseos_repos(self):
        # TODO(mattymo): parse all repo metadata
        repo_names = {
            'base': 'ubuntu',
            'updates': 'ubuntu-updates',
            'security': 'ubuntu-security'}

        if self.clear_upstream_repos:
            repos = [
                {"name": "ubuntu", "delete": True},
                {"name": "ubuntu-security", "delete": True},
                {"name": "ubuntu-updates", "delete": True},
                {
                    "type": "deb",
                    "name": SETTINGS.ubuntu_codename,
                    "uri": self.repourl,
                    "suite": SETTINGS.ubuntu_codename,
                    "section": "main",
                    "priority": None,
                },
            ]
        else:
            repos = [
                {"name": SETTINGS.ubuntu_codename, "delete": True},
            ]
            for repo, name in repo_names.items():
                repo_entry = {
                    "type": "deb",
                    "name": name,
                    "uri": self.repourl,
                    "suite": repo,
                    "section": "main universe multiverse",
                    "priority": 1100 if "holdback" in repo else None
                }
                repos.append(repo_entry)

        return repos

    def _get_ubuntu_repos(self):
        ret = []
        for repo in SETTINGS.ubuntu_repos:
            # TODO(sbrzeczkowski): 'replace' below should be removed once
            # we change repos name convention in openstack.yaml
            name = repo.replace('6.1', '')
            repo_entry = {
                "type": "deb",
                "name": name,
                "uri": self.repourl,
                "suite": repo,
                "section": "main restricted",
                "priority": 1100 if "holdback" in repo else 1050,
            }
            ret.append(repo_entry)

        return ret

    def _get_centos_repos(self):
        ret = []
        for repo in SETTINGS.centos_repos:
            repo_entry = {
                "type": "rpm",
                "name": repo,
                "uri": self.repourl,
                "priority": 20}

            ret.append(repo_entry)

        return ret

    def show_env_conf(self):
        message = []
        message.append("Your repositories are now ready for use. You will need"
                       " to update your Fuel environment configuration to use"
                       " these repositories.\nNote: Be sure to replace ONLY"
                       " the repositories listed below.")

        if self.showuri:
            for repo in self.repos:
                if repo['type'] == "deb":
                    message.append(
                        "{name}:\ndeb {uri} {suite} {section}".format(
                            name=repo['name'],
                            uri=repo['uri'],
                            suite=repo['suite'],
                            section=repo['section']))
                else:
                    message.append(
                        "{name}:\n{uri}".format(
                            name=repo['name'],
                            uri=repo['uri']))
        else:
            yamldata = {"repos": self.repos}
            message.append(
                "Replace the entire repos section of your "
                "environment using the following commands "
                "(put cluster id in the place of '<cluster_id>'):\n\n  "
                "fuel --env <cluster_id> env --attributes --download\n  "
                "vim cluster_<cluster_id>/attributes.yaml\n  "
                "fuel --env <cluster_id> env --attributes --upload")

            message.append(utils.reindent(
                yaml.safe_dump(yamldata, default_flow_style=False), spaces=10))

        return "\n".join(message)

    def mirror_remote_repository(self):
        if "rsync://" in self.repo_url:
            excl_dirs = "ubuntu/dists/mos?.?/,repodata/"
            download_cmd = ('rsync --exclude="*.key","*.gpg",{excl_dirs} -vPr '
                            '{url} {path}').format(path=self.updates_path,
                                                   excl_dirs=excl_dirs,
                                                   url=self.repo_url)
        else:
            cut_dirs = len(self.repo_url.strip('/').split('/'))
            excl_dirs = "--exclude-directories='ubuntu/dists/mos?.?/,repodata'"
            download_cmd = (
                'wget --recursive --no-parent --no-verbose -R "*.html" -R '
                '"*.gif" -R "*.key" -R "*.gpg" -R "*.dsc" -R "*.tar.gz" '
                '{excl_dirs} --directory-prefix {path} -nH '
                '--cut-dirs={cutd} '
                '{url}').format(excl_dirs=excl_dirs,
                                path=self.updates_path,
                                cutd=cut_dirs,
                                url=self.repo_url)

        logger.info('Started mirroring remote repository...')
        logger.debug('Execute command "%s"', download_cmd)
        if utils.exec_cmd(download_cmd) != 0:
            utils.exit_with_error(
                'Mirroring of remote packages repository failed!')
        else:
            logger.info('Remote repository "{url}" for "{release}" ({distro})'
                        ' was successfully mirrored to {path} folder.'.format(
                            url=self.repo_url,
                            release=self.release,
                            distro=self.distro,
                            path=self.updates_path))
