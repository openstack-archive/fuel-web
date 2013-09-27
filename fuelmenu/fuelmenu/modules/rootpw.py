#!/usr/bin/env python

import urwid
import urwid.raw_display
import urwid.web_display
import logging
import sys
import re
import crypt
import subprocess
from fuelmenu.settings import *
from fuelmenu.common import network, puppet, replace, \
    nailyfactersettings, dialog
from fuelmenu.common.urwidwrapper import *
log = logging.getLogger('fuelmenu.rootpw')
blank = urwid.Divider()

fields = ["PASSWORD", "CONFIRM_PASSWORD"

DEFAULTS = {
    "PASSWORD": {"label": "Enter password",
                 "tooltip": "Use ASCII characters only",
                 "value": ""},
    "CONFIRM_PASSWORD": {"label": "Confirm password",
                         "tooltip": "Use ASCII characters only",
                          "value": ""},
    }


class rootpw(urwid.WidgetWrap):
    def __init__(self, parent):
        self.name = "Root Password"
        self.priority = 60
        self.visible = True
        self.parent = parent
        self.screen = None

    def check(self, args):
        """Validate that all fields have valid values and some sanity checks"""
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

        #Passwords must match
        if responses["PASSWORD"] != responses["CONFIRM_PASSWORD"]:
            errors.append("Passwords do not match.")

        #password must not be empty
        if len(responses["PASSWORD"]) == 0:
            errors.append("Password must not be empty.")

        #password needs to be in ASCII character set
        try:
            asciipw = responses["PASSWORD"].decode('ascii')
        except UnicodeDecodeError:
            errors.append("Password contains non-ASCII characters."

        if len(errors) > 0:
            self.parent.footer.set_text(
                "Errors: %s First error: %s" % (len(errors), errors[0]))
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

        hashed = crypt.crypt(responses["PASSWORD"])
        log.info("Changing root password")
        retcode = subprocess.call(["usermod", "-p", hashed, "root"],
                                  stdout=log,
                                  stderr=log)
        if retcode == 0:
            self.parent.footer.set_text("Changed applied successfully.")
            log.info("Root password successfully changed.")
            #Reset fields
            self.cancel(None)
        else:
            self.parent.footer.set_text("Unable to apply changes. Check logs "
                                        "for more details.")

    def cancel(self, button):
        for index, fieldname in enumerate(fields):
            if fieldname == "blank":
                pass
            else:
                self.edits[index].set_edit_text(DEFAULTS[fieldname]['value'])


    def refresh(self):
        pass

    def screenUI(self):
        #Define your text labels, text fields, and buttons first
        text1 = urwid.Text("Set root user password")
        text2 = urwid.Text("")

        self.edits = []
        toolbar = self.parent.footer
        for key in fields:
        #for key, values in DEFAULTS.items():
            #Example: key = hostname, label = Hostname, value = fuel-pm
            if key == "blank":
                self.edits.append(blank)
            elif DEFAULTS[key]["value"] == "radio":
                label = TextLabel(DEFAULTS[key]["label"])
                choices = ChoicesGroup(self, ["Yes", "No"],
                                       default_value="Yes",
                                       fn=self.radioSelectIface)
                self.edits.append(Columns([label, choices]))
            else:
                caption = DEFAULTS[key]["label"]
                default = DEFAULTS[key]["value"]
                tooltip = DEFAULTS[key]["tooltip"]
                password = "PASSWORD" in key.upper()
                self.edits.append(
                    TextField(key, caption, 23, default, tooltip, toolbar,
                              ispassword))

        #Button to check
        button_check = Button("Check", self.check)
        #Button to revert to previously saved settings
        button_cancel = Button("Cancel", self.cancel)
        #Button to apply (and check again)
        button_apply = Button("Apply", self.apply)

        #Wrap buttons into Columns so it doesn't expand and look ugly
        check_col = Columns([button_check, button_cancel,
                             button_apply, ('weight', 2, blank)])

        self.listbox_content = [text1, blank, text2, blank]
        self.listbox_content.extend(self.edits)
        self.listbox_content.append(blank)
        self.listbox_content.append(check_col)

        #Add listeners

        #Build all of these into a list

        #Add everything into a ListBox and return it
        self.listwalker = urwid.SimpleListWalker(self.listbox_content)
        screen = urwid.ListBox(self.listwalker)
        return screen

