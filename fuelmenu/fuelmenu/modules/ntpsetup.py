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
from fuelmenu.common.modulehelper import ModuleHelper
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


class ntpsetup(urwid.WidgetWrap):
    def __init__(self, parent):
        self.name = "Time Sync"
        self.priority = 60
        self.visible = True
        self.deployment = "pre"
        self.parent = parent

        #UI details
        self.header_content = ["NTP Setup", "Note: If you continue without "
                               "NTP, you may have issues with deployment "
                               "due to time synchronization issues. These "
                               "problems are exacerbated in virtualized "
                               "environments."]

        self.fields = ["ntpenabled", "NTP1", "NTP2", "NTP3"]
        self.defaults = \
            {
                "ntpenabled": {"label": "Enable NTP:",
                               "tooltip": "",
                               "value": "radio"},
                "NTP1": {"label": "NTP Server 1:",
                         "tooltip": "NTP Server for time synchronization",
                         "value": "time.nist.gov"},
                "NTP2": {"label": "NTP Server 2:",
                         "tooltip": "NTP Server for time synchronization",
                         "value": "time-a.nist.gov"},
                "NTP3": {"label": "NTP Server 3:",
                         "tooltip": "NTP Server for time synchronization",
                         "value": "time-b.nist.gov"},
            }

        #Load info
        self.gateway = self.get_default_gateway_linux()

        self.oldsettings = self.load()
        self.screen = None

    def check(self, args):
        """Validate that all fields have valid values and sanity checks."""
        self.parent.footer.set_text("Checking data...")
        self.parent.refreshScreen()
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

        ###Validate each field
        errors = []
        warnings = []
        if responses['ntpenabled'] == "No":
            #Disabled NTP means passing no NTP servers to save method
            responses = {
                'NTP1': "",
                'NTP2': "",
                'NTP3': ""}
            self.parent.footer.set_text("No errors found.")
            log.info("No errors found")
            return responses
        if all(map(lambda f: (len(responses[f]) == 0), self.fields)):
            pass
            #We will allow empty if user doesn't need external networking
            #and present a strongly worded warning
            #msg = "If you continue without NTP, you may have issues with "\
            #      + "deployment due to time synchronization issues. These "\
            #      + "problems are exacerbated in virtualized deployments."

            #dialog.display_dialog(
            #    self, widget.TextLabel(msg), "Empty NTP Warning")
        del responses['ntpenabled']
        for ntpfield, ntpvalue in responses.iteritems():
            #NTP must be under 255 chars
            if len(ntpvalue) >= 255:
                errors.append("%s must be under 255 chars." %
                              self.defaults[ntpfield]['label'])

            #NTP needs to have valid chars
            if re.search('[^a-zA-Z0-9-.]', ntpvalue):
                errors.append("%s contains illegal characters." %
                              self.defaults[ntpfield]['label'])

            #ensure external NTP is valid
            if len(ntpvalue) > 0:
                #Validate first NTP address
                try:
                    #Try to test NTP via ntpdate
                    if not self.checkNTP(ntpvalue):
                        warnings.append("%s unable to perform NTP."
                                        % self.defaults[ntpfield]['label'])
                except Exception:
                    warnings.append("%s unable to sync time with server.: %s"
                                    % self.defaults[ntpfield]['label'])
        if len(errors) > 0:
            self.parent.footer.set_text(
                "Errors: %s First error: %s" % (len(errors), errors[0]))
            log.error("Errors: %s %s" % (len(errors), errors))
            return False
        else:
            if len(warnings) > 0:
                msg = ["NTP configuration has the following warnings:"]
                msg.extend(warnings)
                msg.append("You may see errors during provisioning and "
                           "in system logs. NTP errors are not fatal.")
                warning_msg = '\n'.join(str(line) for line in msg)
                dialog.display_dialog(self, widget.TextLabel(warning_msg),
                                      "NTP Warnings")
                log.warning(warning_msg)
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
        ModuleHelper.cancel(self, button)

    def get_default_gateway_linux(self):
        return ModuleHelper.get_default_gateway_linux()

    def load(self):
        #Read in yaml
        defaultsettings = Settings().read(self.parent.defaultsettingsfile)
        oldsettings = defaultsettings
        oldsettings.update(Settings().read(self.parent.settingsfile))

        oldsettings = Settings().read(self.parent.settingsfile)
        for setting in self.defaults.keys():
            try:
                if setting == "ntpenabled":
                    rb_group = \
                        self.edits[self.fields.index("ntpenabled")].rb_group
                    if oldsettings[setting]["value"] == "Yes":
                        rb_group[0].set_state(True)
                        rb_group[1].set_state(False)
                    else:
                        rb_group[0].set_state(False)
                        rb_group[1].set_state(True)
                elif "/" in setting:
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

        Settings().write(newsettings,
                         defaultsfile=self.parent.defaultsettingsfile,
                         outfn=self.parent.settingsfile)

        #Set oldsettings to reflect new settings
        self.oldsettings = newsettings
        #Update defaults
        for index, fieldname in enumerate(self.fields):
            if fieldname != "blank" and fieldname in newsettings:
                self.defaults[fieldname]['value'] = newsettings[fieldname]

    def checkNTP(self, server):
        #Note: Python's internal resolver caches negative answers.
        #Therefore, we should call dig externally to be sure.

        noout = open('/dev/null', 'w')
        ntp_works = subprocess.call(["ntpdate", "-q", "-t2", server],
                                    stdout=noout, stderr=noout)
        return (ntp_works == 0)

    def refresh(self):
        self.gateway = self.get_default_gateway_linux()
        log.info("refresh. gateway is %s" % self.gateway)
        #If gateway is empty, disable NTP
        if self.gateway is None:
            for index, fieldname in enumerate(self.fields):
                if fieldname == "ntpenabled":
                    log.info("clearing ntp enabled")
                    log.info("fieldname: %s" % fieldname)
                    rb_group = self.edits[index].rb_group
                    rb_group[0].set_state(False)
                    rb_group[1].set_state(True)

    def radioSelect(self, current, state, user_data=None):
        """Update network details and display information."""
        ### This makes no sense, but urwid returns the previous object.
        ### The previous object has True state, which is wrong.
        ### Somewhere in current.group a RadioButton is set to True.
        ### Our quest is to find it.
        for rb in current.group:
            if rb.get_label() == current.get_label():
                continue
            if rb.base_widget.state is True:
                self.extdhcp = (rb.base_widget.get_label() == "Yes")
                break

    def screenUI(self):
        return ModuleHelper.screenUI(self, self.header_content, self.fields,
                                     self.defaults)
