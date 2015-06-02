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
import re
import subprocess
import urwid
import urwid.raw_display
import urwid.web_display
log = logging.getLogger('fuelmenu.proxy')
blank = urwid.Divider()


class proxy(urwid.WidgetWrap):
    def __init__(self, parent):
        self.name = "Proxy Setup"
        self.priority = 80
        self.visible = True
        self.deployment = "pre"
        self.parent = parent

        #UI details
        self.header_content = ["Proxy Setup", "Note: If you require a proxy"
                               "to access the Internet, you should configure "
                               "it. If you plan to use fuel-createmirror, "
                               "you need to enable an rsync proxy as well."]

        self.fields = ["proxyenabled", "http_proxy", "RSYNC_PROXY"]
        self.defaults = \
            {
                "proxyenabled": {"label": "Enable Proxy:",
                                 "tooltip": "",
                                 "value": "radio"},
                "http_proxy": {"label": "HTTP Proxy:",
                               "tooltip": "Example: http://myproxy:3128",
                               "value": ""},
                "RSYNC_PROXY": {"label": "Rsync Proxy:",
                                "tooltip": "Example: rsync://myproxy:3128",
                                "value": ""},
            }

        self.oldsettings = self.load()
        self.screen = None
        self.proxyfile = "/etc/profile.d/proxy.sh"

    def check(self, args):
        """Validate that all fields have valid values and sanity checks."""
        self.parent.footer.set_text("Checking data...")
        self.parent.refreshScreen()
        #Get field information
        responses = dict()

        for index, fieldname in enumerate(self.fields):
            if fieldname == "blank":
                pass
            elif fieldname == "proxyenabled":
                rb_group = self.edits[index].rb_group
                if rb_group[0].state:
                    responses["proxyenabled"] = "Yes"
                else:
                    responses["proxyenabled"] = "No"
            else:
                responses[fieldname] = self.edits[index].get_edit_text()

        ###Validate each field
        errors = []
        if responses['proxyenabled'] == "No":
            #Disabled means passing no proxy entries to save method
            responses['http_proxy'] = ""
            responses['RSYNC_PROXY'] = ""

            self.parent.footer.set_text("No errors found.")
            log.info("No errors found")
            return responses

        del responses['proxyenabled']
        for field, value in responses.iteritems():
            #value must be under 255 chars
            if len(value) >= 255:
                errors.append("%s must be under 255 chars." %
                              self.defaults[field]['label'])

            #Proxy needs to have valid chars (plus possible user:pass format)
            if re.search('[ \\\'"]', value):
                errors.append("%s contains invalid characters." %
                              self.defaults[field]['label'])

            #TODO(mattymo): validate proxy values

        if len(errors) > 0:
            self.parent.footer.set_text(
                "Errors: %s First error: %s" % (len(errors), errors[0]))
            log.error("Errors: %s %s" % (len(errors), errors))
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
        #Apply proxy values to proxyfile
        out = open(self.proxyfile, 'w')
        cmd = ""
        if len(responses['http_proxy']) > 0:
            cmd += "export http_proxy={0}\n".format(responses['http_proxy'])
        if len(responses['RSYNC_PROXY']) > 0:
            cmd += "export RSYNC_PROXY={0}\n".format(responses['RSYNC_PROXY'])
        if len(cmd) > 0:
            p = subprocess.Popen(['cat'], stdout=out, stdin=subprocess.PIPE)
            p.communicate(input=cmd)
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
                if setting == "proxyenabled":
                    rb_group = \
                        self.edits[self.fields.index("proxyenabled")].rb_group
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

    def refresh(self):
        pass

    def radioSelect(self, current, state, user_data=None):
        """Update network details and display information."""
        for rb in current.group:
            if rb.get_label() == current.get_label():
                continue
            if rb.base_widget.state is True:
                break

    def screenUI(self):
        return ModuleHelper.screenUI(self, self.header_content, self.fields,
                                     self.defaults)
