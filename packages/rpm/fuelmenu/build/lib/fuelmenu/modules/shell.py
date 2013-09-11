#!/usr/bin/env python

import urwid
import urwid.raw_display
import urwid.web_display
from fuelmenu.common.urwidwrapper import *
import subprocess
import os
import pty

blank = urwid.Divider()

class shell():
  def __init__(self, parent):
    self.name="Shell Login"
    self.priority=99
    self.visible=True
    self.parent=parent
    self.screen = None
    #self.screen = self.screenUI()
  def check(self):
    #TODO: Ensure all params are filled out and sensible
    return True

  def start_shell(self, args):
    self.parent.mainloop.screen.stop()
    message="Type exit to return to the main UI."

    subprocess.call("clear ; echo '%s';echo;bash -i" % message, shell=True)
    self.parent.mainloop.screen.start()

  def refresh(self):
    pass

  def screenUI(self):
    #Define your text labels, text fields, and buttons first
    text1 = urwid.Text("Press the button below to enter a shell login.")
    login_button = Button("Shell Login",self.start_shell)
    #Build all of these into a list
    listbox_content = [ text1, blank, login_button ]
   
    #Add everything into a ListBox and return it
    screen = urwid.ListBox(urwid.SimpleListWalker(listbox_content))
    return screen
    
