#!/usr/bin/env python

import urwid
import urwid.raw_display
import urwid.web_display
from fuelmenu.common.urwidwrapper import *
from fuelmenu.common import dialog
import subprocess
import time
blank = urwid.Divider()


class saveandquit():
    def __init__(self, parent):
        self.name = "Save & Quit"
        self.priority = 99
        self.visible = True
        self.parent = parent
        self.screen = None
        #self.screen = self.screenUI()

    def save_and_exit(self, args):
        results, modulename = self.parent.global_save()
        if results:
           self.parent.footer.set_text("All changes saved successfully!")
           self.parent.refreshScreen()
           time.sleep(1.5)
           self.parent.exit_program(None)
        else:
           #show pop up with more details
           msg = "ERROR: Module %s failed to save. Go back" % (modulename)\
                 + " and fix any mistakes or choose Exit without Saving."
           diag = dialog.display_dialog(self, TextLabel(msg),
                                        "Error saving changes!")

    def exit_without_saving(self, args):
        self.parent.exit_program(None)

    def refresh(self):
        pass

    def screenUI(self):
        #Define your text labels, text fields, and buttons first
        text1 = urwid.Text("Save configuration before you exit?")
        saveandexit_button = Button("Save and Exit", self.save_and_exit)
        exitwithoutsaving_button = Button("Exit without saving",
                                          self.exit_without_saving)
        #Build all of these into a list
        listbox_content = [text1, blank, saveandexit_button,
                           exitwithoutsaving_button]

        #Add everything into a ListBox and return it
        screen = urwid.ListBox(urwid.SimpleListWalker(listbox_content))
        return screen
