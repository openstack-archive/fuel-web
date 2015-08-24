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
import url_access_checker.api as urlck
import url_access_checker.errors as url_errors
import urwid
import urwid.raw_display
import urwid.web_display
log = logging.getLogger('fuelmenu.mirrors')
blank = urwid.Divider()

VERSION_YAML_FILE = '/etc/nailgun/version.yaml'
FUEL_BOOTSTRAP_IMAGE_CONF = '/etc/fuel-bootstrap-image.conf'
BOOTSTRAP_FLAVOR_KEY = 'BOOTSTRAP/flavor'
DISTRO_SUITES_TMPL = ('{distro_release} {distro_release}-security '
                      '{distro_release}-updates')
MOS_MIRROR_TMPL = 'http://mirror.fuel-infra.org/mos-repos/ubuntu/{mos_version}'
MOS_SUITES_TMPL = ('mos{mos_version} mos{mos_version}-security '
                   'mos{mos_version}-updates mos{mos_version}-holdback')


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
        self._bootstrap_flavor = None

        # UI Text
        self.header_content = ["Bootstrap image configuration"]
        fields = (
            'flavor',
            'DISTRO_MIRROR',
            'DISTRO_SUITES',
            'DISTRO_SECTIONS',
            'MOS_MIRROR',
            'MOS_SUITES',
            'MOS_SECTIONS',
            'HTTP_PROXY',
            'EXTRA_DEB_REPOS')
        self.fields = ['BOOTSTRAP/{0}'.format(var) for var in fields]
        # TODO(asheplyakov):
        # switch to the new MOS APT repo structure when it's ready
        distro_suites_dflt = DISTRO_SUITES_TMPL.format(
            distro_release=self.distro_release)
        mos_mirror_dflt = MOS_MIRROR_TMPL.format(mos_version=self.mos_version)
        mos_suites_dflt = MOS_SUITES_TMPL.format(mos_version=self.mos_version)
        self.defaults = {
            BOOTSTRAP_FLAVOR_KEY: {
                "label": "Flavor",
                "tooltip": "",
                "value": "radio",
                "choices": ["CentOS", "Ubuntu (EXPERIMENTAL)"]},
            "BOOTSTRAP/DISTRO_MIRROR": {
                "label": "Ubuntu mirror",
                "tooltip": "Ubuntu APT repo URL",
                "value": "http://archive.ubuntu.com/ubuntu"},
            "BOOTSTRAP/DISTRO_SUITES": {
                "label": "Ubuntu suites",
                "tooltip": "Space separated list of suites. "
                           "E.g. 'trusty trusty-security trusty-updates'. "
                           "First suite in will be used for debootstrap",
                "value": distro_suites_dflt},
            "BOOTSTRAP/DISTRO_SECTIONS": {
                "label": "Ubuntu sections",
                "tooltip": "Space separated list of sections. "
                           "E.g. main universe",
                "value": "main universe multiverse restricted"},
            "BOOTSTRAP/MOS_MIRROR": {
                "label": "MOS mirror",
                "tooltip": ("MOS APT repo URL (can use file:// protocol, will"
                            "use local mirror in such case"),
                "value": mos_mirror_dflt},
            "BOOTSTRAP/MOS_SUITES": {
                "label": "MOS suites",
                "tooltip": "Space separated list of suites. "
                           "E.g. mos7.0 mos7.0-security",
                "value": mos_suites_dflt},
            "BOOTSTRAP/MOS_SECTIONS": {
                "label": "MOS sections",
                "tooltip": "Space separated list of sections. "
                           "E.g. main restricted",
                "value": "main"},
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
            if fieldname == 'blank':
                pass
            elif fieldname == BOOTSTRAP_FLAVOR_KEY:
                rb_group = self.edits[index].rb_group
                flavor = 'centos' if rb_group[0].state else 'ubuntu'
                ret[fieldname] = flavor
            else:
                ret[fieldname] = self.edits[index].get_edit_text()
        return ret

    def check(self, args):
        """Validate that all fields have valid values through sanity checks."""
        self.parent.footer.set_text("Checking data...")
        self.parent.refreshScreen()
        responses = self.responses

        errors = []

        # APT repo URL must not be empty
        distro_mirror= responses['BOOTSTRAP/DISTRO_MIRROR'].strip()
        distro_suites = responses['BOOTSTRAP/DISTRO_SUITES'].strip()
        distro_sections = responses['BOOTSTRAP/DISTRO_SECTIONS'].strip()
        mos_mirror = responses['BOOTSTRAP/MOS_MIRROR'].strip()
        mos_suites = responses['BOOTSTRAP/MOS_SUITES'].strip()
        mos_sections = responses['BOOTSTRAP/MOS_SECTIONS'].strip()
        http_proxy = responses['BOOTSTRAP/HTTP_PROXY'].strip()

        if len(distro_mirror) == 0:
            errors.append("Ubuntu mirror URL must not be empty.")

        if len(distro_suites) == 0:
            errors.append("Ubuntu suites must contain at least one suite. "
                          "E.g. 'trusty trusty-security trusty-updates'")

        if len(distro_suites) == 0:
            errors.append("Ubuntu sections must contain at least one section. "
                          "E.g. 'main universe multiverse restricted'")

        release_url_tmpl = '{mirror}/dists/{suite}/Release'

        # Check if all distro suites are available
        for distro_suite in distro_suites.split():
            if not self.check_url(release_url_tmpl.format(
                mirror=distro_mirror, suite=distro_suite), http_proxy):
                errors.append(
                    "Repository {mirror} {suite} is not accessible.".format(
                        mirror=distro_mirror, suite=distro_suite))

        # TODO(asheplyakov):
        # check if it's possible to debootstrap with distro mirror
        # and first suite in the list of distro suites.

        if len(mos_mirror) == 0:
            errors.append("MOS repo URL must not be empty.")

        if len(mos_suites) == 0:
            errors.append("MOS suites must contain at least one suite. "
                          "E.g. 'mos7.0 mos7.0-updates'.")

        if len(mos_sections) == 0:
            errors.append("MOS sections must contain at least one section. "
                          "E.g. 'main restricted'.")

        # Check if all mos suites are available
        for mos_suite in mos_suites.split():
            if not self.check_url(release_url_tmpl.format(
                mirror=mos_mirror, suite=mos_suite), http_proxy):
                errors.append(
                    "Repository {mirror} {suite} is not accessible.".format(
                        mirror=mos_mirror, suite=mos_suite))

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

    def _ui_set_bootstrap_flavor(self):
        rb_index = self.fields.index(BOOTSTRAP_FLAVOR_KEY)
        is_ubuntu = self._bootstrap_flavor is not None and \
            'ubuntu' in self._bootstrap_flavor
        try:
            rb_group = self.edits[rb_index].rb_group
            rb_group[0].set_state(not is_ubuntu)
            rb_group[1].set_state(is_ubuntu)
        except AttributeError:
            # the UI hasn't been initalized yet
            pass

    def _set_bootstrap_flavor(self, flavor):
        is_ubuntu = flavor is not None and 'ubuntu' in flavor.lower()
        self._bootstrap_flavor = 'ubuntu' if is_ubuntu else 'centos'
        self._ui_set_bootstrap_flavor()

    def load(self):
        # Read in yaml
        defaultsettings = Settings().read(self.parent.defaultsettingsfile)
        oldsettings = defaultsettings
        oldsettings.update(Settings().read(self.parent.settingsfile))

        for setting in self.defaults:
            try:
                if BOOTSTRAP_FLAVOR_KEY == setting:
                    section, key = BOOTSTRAP_FLAVOR_KEY.split('/')
                    flavor = oldsettings[section][key]
                    self._set_bootstrap_flavor(flavor)
                elif "/" in setting:
                    part1, part2 = setting.split("/")
                    self.defaults[setting]["value"] = oldsettings[part1][part2]
                else:
                    self.defaults[setting]["value"] = oldsettings[setting]
            except KeyError:
                log.warning("no setting named %s found.", setting)
            except Exception as e:
                log.warning("unexpected error: %s", e.message)
        return oldsettings

    def save(self, responses):
        # Generic settings start
        newsettings = dict()
        for setting in responses.keys():
            if "/" in setting:
                part1, part2 = setting.split("/")
                if part1 not in newsettings:
                    # We may not touch all settings, so copy oldsettings first
                    newsettings[part1] = self.oldsettings[part1]
                newsettings[part1][part2] = responses[setting]
            else:
                newsettings[setting] = responses[setting]
        # Generic settings end

        Settings().write(newsettings,
                         defaultsfile=self.parent.defaultsettingsfile,
                         outfn=self.parent.settingsfile)

        # Set oldsettings to reflect new settings
        self.oldsettings = newsettings
        # Update self.defaults
        for index, fieldname in enumerate(self.fields):
            if fieldname != "blank":
                log.info("resetting %s", fieldname)
                if fieldname not in self.defaults.keys():
                    log.error("no such field: %s, valid are %s",
                              fieldname, ' '.join(self.defaults.keys()))
                    continue
                if fieldname not in newsettings.keys():
                    log.error("newsettings: no such field: %s, valid are %s",
                              fieldname, ' '.join(newsettings.keys()))
                    continue
                self.defaults[fieldname]['value'] = newsettings[fieldname]

    def check_url(self, url, http_proxy):
        try:
            return urlck.check_urls([url], proxies={'http': http_proxy})
        except url_errors.UrlNotAvailable:
            return False

    def radioSelect(self, current, state, user_data=None):
        pass

    def refresh(self):
        pass

    def screenUI(self):
        screen = ModuleHelper.screenUI(self, self.header_content, self.fields,
                                       self.defaults)
        # set the radiobutton state (ModuleHelper handles only yes/no choice)
        self._ui_set_bootstrap_flavor()
        return screen
