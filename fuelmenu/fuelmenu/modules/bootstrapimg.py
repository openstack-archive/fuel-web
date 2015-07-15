#!/usr/bin/env python
# Copyright 2015 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from fuelmenu.common.modulehelper import ModuleHelper
from fuelmenu.settings import Settings
import logging
import os
import url_access_checker.api as urlck
import urwid
import urwid.raw_display
import urwid.web_display
log = logging.getLogger('fuelmenu.mirrors')
blank = urwid.Divider()

VERSION_YAML_FILE = '/etc/nailgun/version.yaml'
FUEL_BOOTSTRAP_IMAGE_CONF = '/etc/fuel-bootstrap-image.conf'


class bootstrapimg(urwid.WidgetWrap):
    def __init__(self, parent):
        self.name = "Bootstrap Image"
        self.priority = 55
        self.visible = True
        self.deployment = "pre"
        self.parent = parent
        self.distro = 'ubuntu'
        self._distro_release = None
        self._mos_version = None

        #UI Text
        self.header_content = ["Bootstrap image configuration"]
        fields = (
            'MIRROR_DISTRO',
            'MIRROR_MOS',
            'HTTP_PROXY',
            'EXTRA_DEB_REPOS')
        self.fields = ['BOOTSTRAP/{0}'.format(var) for var in fields]
        # TODO(asheplyakov):
        # switch to the new MOS APT repo structure when it's ready
        mos_repo_dflt = 'http://mirror.fuel-infra.org/mos-repos'\
            '/{mos_version}/cluster/base/{distro_release}'.format(
                mos_version=self.mos_version,
                distro_release=self.distro_release)
        self.defaults = {
            "BOOTSTRAP/MIRROR_DISTRO": {
                "label": "Ubuntu mirror",
                "tooltip": "Ubuntu APT repo URL",
                "value": "http://archive.ubuntu.com/ubuntu"},
            "BOOTSTRAP/MIRROR_MOS": {
                "label": "MOS mirror",
                "tooltip": "MOS APT repo URL",
                "value": mos_repo_dflt},
            "BOOTSTRAP/HTTP_PROXY": {
                "label": "HTTP proxy",
                "tooltip": "Use this proxy when building the bootstrap image",
                "value": ""},
            "BOOTSTRAP/EXTRA_DEB_REPOS": {
                "label": "Extra APT repositories",
                "tooltip": "Additional repositories for bootstrap image",
                "value": ""}
        }
        self.oldsettings = self.load()
        self.screen = None

    def _read_version_info(self):
        settings = Settings()
        dat = settings.read(VERSION_YAML_FILE)
        version_info = dat['VERSION']
        self._mos_version = version_info['release']
        self._distro_release = version_info.get('ubuntu_release', 'trusty')

    @property
    def mos_version(self):
        if not self._mos_version:
            self._read_version_info()
        return self._mos_version

    @property
    def distro_release(self):
        if not self._distro_release:
            self._read_version_info()
        return self._distro_release

    @property
    def responses(self):
        ret = dict()
        for index, fieldname in enumerate(self.fields):
            if fieldname != 'blank':
                ret[fieldname] = self.edits[index].get_edit_text()
        return ret

    def check(self, args):
        """Validate that all fields have valid values through sanity checks."""
        self.parent.footer.set_text("Checking data...")
        self.parent.refreshScreen()
        responses = self.responses

        errors = []

        # APT repo URL must not be empty
        distro_repo_base = responses['BOOTSTRAP/MIRROR_DISTRO'].strip()
        mos_repo_base = responses['BOOTSTRAP/MIRROR_MOS'].strip()
        http_proxy = responses['BOOTSTRAP/HTTP_PROXY'].strip()

        if len(distro_repo_base) == 0:
            errors.append("Ubuntu mirror URL must not be empty.")

        if not self.checkDistroRepo(distro_repo_base, http_proxy):
            errors.append("Ubuntu repository is not accessible.")

        if len(mos_repo_base) == 0:
            errors.append("MOS repo URL must not be empty.")

        if not self.checkMOSRepo(mos_repo_base, http_proxy):
            errors.append("MOS repository is not accessible.")

        if len(errors) > 0:
            self.parent.footer.set_text("Error: %s" % (errors[0]))
            log.error("Errors: %s %s" % (len(errors), errors))
            return False
        else:
            self.parent.footer.set_text("No errors found.")
            return responses

    def apply(self, args):
        responses = self.check(args)
        if responses is False:
            log.error("Check failed. Not applying")
            log.error("%s" % (responses))
            return False

        with open(FUEL_BOOTSTRAP_IMAGE_CONF, "w") as fbiconf:
            for var in self.fields:
                scope, name = var.split('/')
                fbiconf.write('{0}="{1}"\n'.format(name, responses.get(var)))
            fbiconf.write('MOS_VERSION="{0}"'.format(self.mos_version))
        self.save(responses)
        return True

    def cancel(self, button):
        ModuleHelper.cancel(self, button)

    def load(self):
        #Read in yaml
        defaultsettings = Settings().read(self.parent.defaultsettingsfile)
        oldsettings = defaultsettings
        oldsettings.update(Settings().read(self.parent.settingsfile))

        for setting in self.defaults:
            try:
                if "/" in setting:
                    part1, part2 = setting.split("/")
                    self.defaults[setting]["value"] = oldsettings[part1][part2]
                else:
                    self.defaults[setting]["value"] = oldsettings[setting]
            except Exception:
                log.warning("No setting named %s found." % setting)
                continue
        return oldsettings

    def save(self, responses):
        ## Generic settings start ##
        newsettings = dict()
        for setting in responses.keys():
            if "/" in setting:
                part1, part2 = setting.split("/")
                if part1 not in newsettings:
                #We may not touch all settings, so copy oldsettings first
                    newsettings[part1] = self.oldsettings[part1]
                newsettings[part1][part2] = responses[setting]
            else:
                newsettings[setting] = responses[setting]
        ## Generic settings end ##

        log.info("new settings {0}", str(newsettings))
        Settings().write(newsettings,
                         defaultsfile=self.parent.defaultsettingsfile,
                         outfn=self.parent.settingsfile)

        #Set oldsettings to reflect new settings
        self.oldsettings = newsettings
        #Update self.defaults
        for index, fieldname in enumerate(self.fields):
            if fieldname != "blank":
                log.info("resetting {0}".format(fieldname))
                if fieldname not in self.defaults.keys():
                    log.error("no such field: {0}, valid are {1}",
                              fieldname, ' '.join(self.defaults.keys()))
                    continue
                if fieldname not in newsettings.keys():
                    log.error("newsettings: no such field: {0}, valid are {1}",
                              fieldname, ' '.join(newsettings.keys()))
                    continue
                self.defaults[fieldname]['value'] = newsettings[fieldname]

    def check_url(self, url, http_proxy):
        available = True
        # XXX: check_urls does not accept proxy settings as an argument,
        # pass them via the environment. Be careful to restore the previous
        # value of the environment variable (including null)
        old_http_proxy = os.environ.get('HTTP_PROXY')
        if http_proxy:
            os.environ['HTTP_PROXY'] = http_proxy
        else:
            try:
                del os.environ['HTTP_PROXY']
            except KeyError:
                pass
        try:
            urlck.check_urls([url])
        except Exception:
            log.debug("can't download {0}, "
                      "network problem or a wrong URL", url)
            available = False
        if old_http_proxy:
            os.environ['HTTP_PROXY'] = old_http_proxy
        else:
            try:
                del os.environ['HTTP_PROXY']
            except KeyError:
                pass
        return available

    def checkDistroRepo(self, base_url, http_proxy):
        release_url = '{base_url}/dists/{distro_release}/Release'.format(
            base_url=base_url, distro_release=self.distro_release)
        available = self.check_url(release_url, http_proxy)
        # TODO(asheplyakov):
        # check if it's possible to debootstrap with this repo
        return available

    def checkMOSRepo(self, base_url, http_proxy):
        # deb {repo_base_url}/mos/ubuntu mos{mos_version} main
        # TODO(asheplyakov): current MOS APT repo structre is badly broken,
        # so we have
        # deb {base_url}/mos-repos/{mos_version}/cluster/base/trusy trusty main
        # instead. Update release_url after fixing the repo structure.

        release_url = '{base_url}/dists/{distro_release}/Release'.format(
            base_url=base_url, distro_release=self.distro_release)
        available = self.check_url(release_url, http_proxy)
        return available

    def radioSelect(self, current, state, user_data=None):
        pass

    def refresh(self):
        pass

    def screenUI(self):
        return ModuleHelper.screenUI(self, self.header_content, self.fields,
                                     self.defaults)
