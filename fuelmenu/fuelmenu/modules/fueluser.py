#!/usr/bin/env python
# Copyright 2014 Mirantis, Inc.
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
import urwid
import urwid.raw_display
import urwid.web_display

log = logging.getLogger('fuelmenu.rootpw')
blank = urwid.Divider()


class fueluser(urwid.WidgetWrap):
    def __init__(self, parent):
        self.name = "Fuel User"
        self.priority = 70
        self.visible = True
        self.parent = parent
        #UI text
        self.header_content = ["Set Fuel user password", "Default user: admin",
                               "Default pass: admin", ""]
        self.fields = ["FUEL_ACCESS/password", "CONFIRM_PASSWORD"]
        self.defaults = \
            {
                "FUEL_ACCESS/password": {"label": "Fuel password",
                                         "tooltip": "ASCII characters only",
                                         "value": ""},
                "CONFIRM_PASSWORD": {"label": "Confirm password",
                                     "tooltip": "ASCII characters only",
                                     "value": ""},
            }

        self.oldsettings = self.load()
        self.screen = None

    def check(self, args):
        """Validate that all fields have valid values and sanity checks."""
        self.parent.footer.set_text("Checking data...")
        self.parent.refreshScreen()
        #Get field information
        responses = dict()

        for index, fieldname in enumerate(self.fields):
            if fieldname != "blank":
                responses[fieldname] = self.edits[index].get_edit_text()

        ###Validate each field
        errors = []

        #Passwords must match
        if responses["FUEL_ACCESS/password"] != responses["CONFIRM_PASSWORD"]:
            errors.append("Passwords do not match.")

        #password must not be empty
        if len(responses["FUEL_ACCESS/password"]) == 0:
            errors.append("Password must not be empty.")

        #password needs to be in ASCII character set
        try:
            if responses["FUEL_ACCESS/password"].decode('ascii'):
                pass
        except UnicodeDecodeError:
            errors.append("Password contains non-ASCII characters.")

        if len(errors) > 0:
            self.parent.footer.set_text("Error: %s" % (errors[0]))
            log.error("Errors: %s %s" % (len(errors), errors))
            return False
        else:
            self.parent.footer.set_text("No errors found.")
            #Remove confirm from responses so it isn't saved
            del responses["CONFIRM_PASSWORD"]
            #Add username for config file
            #responses["FUEL_ACCESS/user"] = "admin"
            return responses

    def apply(self, args):
        responses = self.check(args)
        if responses is False:
            log.error("Check failed. Not applying")
            log.error("%s" % (responses))
            for index, fieldname in enumerate(self.fields):
                if fieldname == "FUEL_ACCESS/password":
                    return (self.edits[index].get_edit_text() == "")
            return False
        self.save(responses)
        return True

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
        Settings().write(newsettings,
                         defaultsfile=self.parent.defaultsettingsfile,
                         outfn=self.parent.settingsfile)

        self.parent.footer.set_text("Changes applied successfully.")
        #Reset fields
        log.error("precancel")
        self.cancel(None)
        log.error("postcancel")

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

    def cancel(self, button):
        ModuleHelper.cancel(self, button)

    def refresh(self):
        pass

    def screenUI(self):
        return ModuleHelper.screenUI(self, self.header_content, self.fields,
                                     self.defaults)
