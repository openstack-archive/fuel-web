#!/usr/bin/env python
# Copyright 2013 Mirantis, Inc.
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

try:
    from collections import OrderedDict
except Exception:
    # python 2.6 or earlier use backport
    from ordereddict import OrderedDict
from fuelmenu.common.modulehelper import ModuleHelper
from fuelmenu.common import pwgen
from fuelmenu.settings import Settings
import logging
import urwid
import urwid.raw_display
import urwid.web_display
log = logging.getLogger('fuelmenu.servicepws')
blank = urwid.Divider()


class servicepws(urwid.WidgetWrap):
    def __init__(self, parent):
        self.name = "Service Passwords"
        self.priority = 99
        self.visible = False
        self.parent = parent
        #UI text
        self.header_content = ["Set service passwords", ""]
        self.defaults = \
            {
                "astute/user": {"label": "Astute user",
                                "tooltip": "",
                                "value": "naily"},
                "astute/password": {"label": "Astute password",
                                    "tooltip": "",
                                    "value": pwgen.password()},
                "cobbler/user": {"label": "Cobbler user",
                                 "tooltip": "",
                                 "value": "cobbler"},
                "cobbler/password": {"label": "Cobbler password",
                                     "tooltip": "",
                                     "value": pwgen.password()},
                "keystone/admin_token": {"label": "Keystone Admin Token",
                                         "tooltip": "",
                                         "value": pwgen.password()},
                "keystone/nailgun_user": {
                    "label": "Keystone username for Nailgun",
                    "tooltip": "",
                    "value": "nailgun"},
                "keystone/nailgun_password": {
                    "label": "Keystone password for Nailgun",
                    "tooltip": "",
                    "value": pwgen.password()},
                "keystone/ostf_user": {
                    "label": "Keystone username for OSTF",
                    "tooltip": "",
                    "value": "ostf"},
                "keystone/ostf_password": {
                    "label": "Keystone password for OSTF",
                    "tooltip": "",
                    "value": pwgen.password()},
                "mcollective/user": {"label": "Mcollective user",
                                     "tooltip": "",
                                     "value": "mcollective"},
                "mcollective/password": {"label": "Mcollective password",
                                         "tooltip": "",
                                         "value": pwgen.password()},
                "postgres/keystone_dbname": {"label": "Keystone DB name",
                                             "tooltip": "",
                                             "value": "keystone"},
                "postgres/keystone_user": {"label": "Keystone DB user",
                                           "tooltip": "",
                                           "value": "keystone"},
                "postgres/keystone_password": {"label": "Keystone DB password",
                                               "tooltip": "",
                                               "value": pwgen.password()},
                "postgres/nailgun_dbname": {"label": "Nailgun DB name",
                                            "tooltip": "",
                                            "value": "nailgun"},
                "postgres/nailgun_user": {"label": "Nailgun DB user",
                                          "tooltip": "",
                                          "value": "nailgun"},
                "postgres/nailgun_password": {"label": "Nailgun DB password",
                                              "tooltip": "",
                                              "value": pwgen.password()},
                "postgres/ostf_dbname": {"label": "OSTF DB name",
                                         "tooltip": "",
                                         "value": "ostf"},
                "postgres/ostf_user": {"label": "OSTF DB user",
                                       "tooltip": "",
                                       "value": "ostf"},
                "postgres/ostf_password": {"label": "OSTF DB password",
                                           "tooltip": "",
                                           "value": pwgen.password()},
            }
        self.fields = self.defaults.keys()

        self.oldsettings = self.load()
        self.screen = None

    def check(self, args):
        #Get field information
        responses = dict()

        for index, fieldname in enumerate(self.fields):
            if fieldname == "blank":
                pass
            else:
                responses[fieldname] = self.edits[index].get_edit_text()
        return responses

    def apply(self, args):
        log.debug('start saving servicepws')
        responses = self.check(args)
        if responses is False:
            log.error("Check failed. Not applying")
            log.error("%s" % (responses))
            for index, fieldname in enumerate(self.fields):
                if fieldname == "PASSWORD":
                    return (self.edits[index].get_edit_text() == "")
            return False

        self.save(responses)

    def load(self):
        #Read in yaml
        defaultsettings = Settings().read(self.parent.defaultsettingsfile)
        oldsettings = defaultsettings
        oldsettings.update(Settings().read(self.parent.settingsfile))

        oldsettings = Settings().read(self.parent.settingsfile)
        for setting in self.defaults.keys():
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
        newsettings = OrderedDict()
        for setting in responses.keys():
            if "/" in setting:
                part1, part2 = setting.split("/")
                if part1 not in newsettings:
                #We may not touch all settings, so copy oldsettings first
                    try:
                        newsettings[part1] = self.oldsettings[part1]
                    except Exception:
                        if part1 not in newsettings.keys():
                            newsettings[part1] = OrderedDict()
                        log.warning("issues setting newsettings %s " % setting)
                        log.warning("current newsettings: %s" % newsettings)
                newsettings[part1][part2] = responses[setting]
            else:
                newsettings[setting] = responses[setting]
        Settings().write(newsettings,
                         defaultsfile=self.parent.defaultsettingsfile,
                         outfn=self.parent.settingsfile)

        ## Generic settings end ##
        log.debug('done saving servicepws')

        #Set oldsettings to reflect new settings
        self.oldsettings = newsettings
        #Update defaults
        for index, fieldname in enumerate(self.fields):
            if fieldname != "blank" and fieldname in newsettings:
                self.defaults[fieldname]['value'] = newsettings[fieldname]

    def cancel(self, button):
        ModuleHelper.cancel(self, button)

    def refresh(self):
        pass

    def screenUI(self):
        return ModuleHelper.screenUI(self, self.header_content, self.fields,
                                     self.defaults)
