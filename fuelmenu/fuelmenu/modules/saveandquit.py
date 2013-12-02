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
import time
import urwid
import urwid.raw_display
import urwid.web_display

blank = urwid.Divider()


class saveandquit():
    def __init__(self, parent):
        self.name = "Quit Setup"
        self.priority = 99
        self.visible = True
        self.parent = parent
        self.screen = None
        #UI text
        saveandcontinue_button = widget.Button("Save and Continue",
                                               self.save_and_continue)
        saveandquit_button = widget.Button("Save and Quit", self.save_and_quit)
        quitwithoutsaving_button = widget.Button("Quit without saving",
                                                 self.quit_without_saving)
        self.header_content = ["Save configuration before quitting?", blank,
                               saveandcontinue_button, saveandquit_button,
                               quitwithoutsaving_button]

        self.fields = []
        self.defaults = dict()

    def save_and_continue(self, args):
        self.save()

    def save_and_quit(self, args):
        if self.save():
            self.parent.refreshScreen()
            time.sleep(1.5)
            self.parent.exit_program(None)

    def save(self):
        results, modulename = self.parent.global_save()
        if results:
            self.parent.footer.set_text("All changes saved successfully!")
            return True
        else:
            #show pop up with more details
            msg = "ERROR: Module %s failed to save. Go back" % (modulename)\
                  + " and fix any mistakes or choose Quit without Saving."
            dialog.display_dialog(self, widget.TextLabel(msg),
                                  "Error saving changes!")
            return False

    def quit_without_saving(self, args):
        self.parent.exit_program(None)

    def refresh(self):
        pass

    def screenUI(self):
        return ModuleHelper.screenUI(self, self.header_content, self.fields,
                                     self.defaults, buttons_visible=False)
