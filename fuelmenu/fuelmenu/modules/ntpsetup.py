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

from fuelmenu.common import dialog
from fuelmenu.common import nailyfactersettings
import fuelmenu.common.urwidwrapper as widget
from fuelmenu.settings import Settings
import logging
import re
import subprocess
import urwid
import urwid.raw_display
import urwid.web_display
log = logging.getLogger('fuelmenu.mirrors')
blank = urwid.Divider()

#Need to define fields in order so it will render correctly
fields = ["NTP1", "NTP2", "NTP3"]

DEFAULTS = \
    {
        "NTP1": {"label": "NTP Server 1",
                 "tooltip": "NTP Server for time synchronization",
                 "value": "time.nist.gov"},
        "NTP2": {"label": "NTP Server 3",
                 "tooltip": "NTP Server for time synchronization",
                 "value": "time-a.nist.gov"},
        "NTP3": {"label": "NTP Server 3",
                 "tooltip": "NTP Server for time synchronization",
                 "value": "time-b.nist.gov"},
    }


class ntpsetup(urwid.WidgetWrap):
    def __init__(self, parent):
        self.name = "Time Sync"
        self.priority = 60
        self.visible = True
        self.deployment = "pre"
        self.parent = parent
        self.oldsettings = self.load()
        self.screen = None

    def check(self, args):
        """Validate that all fields have valid values and sanity checks."""
        self.parent.footer.set_text("Checking data...")
        self.parent.refreshScreen()
        #Get field information
        responses = dict()

        for index, fieldname in enumerate(fields):
            if fieldname == "blank":
                pass
            else:
                responses[fieldname] = self.edits[index].get_edit_text()

        ###Validate each field
        errors = []

        if all(map(lambda f: (len(responses[f]) == 0), fields)):
            #We will allow empty if user doesn't need external networking
            #and present a strongly worded warning
            msg = "If you continue without NTP, you may have issues with "\
                  + "deployment due to time synchronization issues. These "\
                  + "problems are exacerbated in virtualized deployments."

            dialog.display_dialog(
                self, widget.TextLabel(msg), "Empty NTP Warning")

        for ntpfield, ntpvalue in responses.iteritems():
            #NTP must be under 255 chars
            if len(ntpvalue) >= 255:
                errors.append("%s must be under 255 chars." %
                              DEFAULTS[ntpfield]['label'])

            #NTP needs to have valid chars
            if re.search('[^a-zA-Z0-9-.]', ntpvalue):
                errors.append("%s contains illegal characters." %
                              DEFAULTS[ntpfield]['label'])

            #ensure external NTP is valid
            if len(ntpvalue) > 0:
                #Validate first NTP address
                try:
                    #Try to test NTP via ntpdate
                    if not self.checkNTP(ntpvalue):
                        errors.append("%s unable to perform NTP."
                                      % DEFAULTS[ntpfield]['label'])
                except Exception as e:
                    errors.append(e)
                    errors.append("%s unable to perform NTP: %s"
                                  % DEFAULTS[ntpfield]['label'])

        if len(errors) > 0:
            self.parent.footer.set_text(
                "Errors: %s First error: %s" % (len(errors), errors[0]))
            log.warning("Errors: %s %s" % (len(errors), errors))
            return False
        else:
            self.parent.footer.set_text("No errors found.")
            log.info("No errors found")
            return responses

    def apply(self, args):
        responses = self.check(args)
        if responses is False:
            log.error("Check failed. Not applying")
            log.error("%s" % (responses))
            return False

        self.save(responses)
        #Apply NTP now
        if len(responses['NTP1']) > 0:
            #Stop ntpd, run ntpdate, start ntpd
            noout = open('/dev/null', 'w')
            subprocess.call(["service", "ntpd", "stop"],
                            stdout=noout, stderr=noout)
            subprocess.call(["ntpdate", "-t5", responses['NTP1']],
                            stdout=noout, stderr=noout)
            subprocess.call(["service", "ntpd", "start"],
                            stdout=noout, stderr=noout)
        return True

    def cancel(self, button):
        for index, fieldname in enumerate(fields):
            if fieldname != "blank":
                self.edits[index].set_edit_text(DEFAULTS[fieldname]['value'])

    def load(self):
        #Read in yaml
        defaultsettings = Settings().read(self.parent.defaultsettingsfile)
        oldsettings = defaultsettings
        oldsettings.update(Settings().read(self.parent.settingsfile))

        oldsettings = Settings().read(self.parent.settingsfile)
        for setting in DEFAULTS.keys():
            try:
                if "/" in setting:
                    part1, part2 = setting.split("/")
                    DEFAULTS[setting]["value"] = oldsettings[part1][part2]
                else:
                    DEFAULTS[setting]["value"] = oldsettings[setting]
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

        Settings().write(newsettings,
                         defaultsfile=self.parent.defaultsettingsfile,
                         outfn=self.parent.settingsfile)
        #Write naily.facts
        factsettings = dict()
        #log.debug(newsettings)
        for key in newsettings.keys():
            if key != "blank":
                factsettings[key] = newsettings[key]
        n = nailyfactersettings.NailyFacterSettings()
        n.write(factsettings)

        #Set oldsettings to reflect new settings
        self.oldsettings = newsettings
        #Update DEFAULTS
        for index, fieldname in enumerate(fields):
            if fieldname != "blank":
                DEFAULTS[fieldname]['value'] = newsettings[fieldname]

    def checkNTP(self, server):
        #Note: Python's internal resolver caches negative answers.
        #Therefore, we should call dig externally to be sure.

        noout = open('/dev/null', 'w')
        ntp_works = subprocess.call(["ntpdate", "-q", "-t2", server],
                                    stdout=noout, stderr=noout)
        return (ntp_works == 0)

    def refresh(self):
        pass

    def radioSelectIface(self):
        pass

    def screenUI(self):
        #Define your text labels, text fields, and buttons first
        text1 = urwid.Text("NTP Setup")
        text2 = urwid.Text("Note: Leave all NTP servers blank if you do not "
                           "have Internet access.")

        self.edits = []
        toolbar = self.parent.footer
        for key in fields:
            #Example: key = hostname, label = Hostname, value = fuel-pm
            if key == "blank":
                self.edits.append(blank)
            elif DEFAULTS[key]["value"] == "radio":
                label = widget.TextLabel(DEFAULTS[key]["label"])
                choices = widget.ChoicesGroup(self, ["Yes", "No"],
                                              default_value="Yes",
                                              fn=self.radioSelectIface)
                self.edits.append(widget.Columns([label, choices]))
            else:
                caption = DEFAULTS[key]["label"]
                default = DEFAULTS[key]["value"]
                tooltip = DEFAULTS[key]["tooltip"]
                self.edits.append(
                    widget.TextField(key, caption, 23, default, tooltip,
                                     toolbar))

        #Button to check
        button_check = widget.Button("Check", self.check)
        #Button to revert to previously saved settings
        button_cancel = widget.Button("Cancel", self.cancel)
        #Button to apply (and check again)
        button_apply = widget.Button("Apply", self.apply)

        #Wrap buttons into Columns so it doesn't expand and look ugly
        if self.parent.globalsave:
            check_col = widget.Columns([button_check])
        else:
            check_col = widget.Columns([button_check, button_cancel,
                                       button_apply, ('weight', 2, blank)])

        self.listbox_content = [text1, blank, text2, blank]
        self.listbox_content.extend(self.edits)
        self.listbox_content.append(blank)
        self.listbox_content.append(check_col)

        #Add listeners

        #Build all of these into a list
        #self.listbox_content = [ text1, blank, blank, edit1, edit2, \
        #                    edit3, edit4, edit5, edit6, button_check ]

        #Add everything into a ListBox and return it
        self.listwalker = urwid.SimpleListWalker(self.listbox_content)
        screen = urwid.ListBox(self.listwalker)
        return screen
