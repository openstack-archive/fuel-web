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

import collections
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
                "astute/user": {"label": "",
                                "tooltip": "",
                                "value": "naily"},
                "astute/password": {"label": "",
                                    "tooltip": "",
                                    "value":  pwgen.password()},
                "cobbler/user": {"label": "",
                                 "tooltip": "",
                                 "value": "cobbler"},
                "cobbler/password": {"label": "",
                                     "tooltip": "",
                                     "value":  pwgen.password()},
                "mcollective/user": {"label": "",
                                     "tooltip": "",
                                     "value": "mcollective"},
                "mcollective/password": {"label": "",
                                         "tooltip": "",
                                         "value":  pwgen.password()},
                "postgres/nailgun_dbname": {"label": "",
                                            "tooltip": "",
                                            "value": "nailgun"},
                "postgres/nailgun_user": {"label": "",
                                          "tooltip": "",
                                          "value": "nailgun"},
                "postgres/nailgun_password": {"label": "",
                                              "tooltip": "",
                                              "value": pwgen.password()},
                "postgres/ostf_dbname": {"label": "",
                                         "tooltip": "",
                                         "value": "ostf"},
                "postgres/ostf_user": {"label": "",
                                       "tooltip": "",
                                       "value": "ostf"},
                "postgres/ostf_password": {"label": "",
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
            elif fieldname == "ntpenabled":
                rb_group = self.edits[index].rb_group
                if rb_group[0].state:
                    responses["ntpenabled"] = "Yes"
                else:
                    responses["ntpenabled"] = "No"
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
