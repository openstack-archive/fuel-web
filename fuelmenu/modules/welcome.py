#!/usr/bin/env python

import urwid
import urwid.raw_display
import urwid.web_display


blank = urwid.Divider()


class welcome():
  def __init__(self, parent):
    self.name="Welcome"
    self.priority=1
    self.visible=True
    self.screen = self.screenUI()

  def check(self):
    #TODO: Ensure all params are filled out and sensible
    return True

  def screenUI(self):
    #Define your text labels, text fields, and buttons first
    text1 = urwid.Text("Welcome to Fuel! Use the menu on the left")
    
    #Build all of these into a list
    listbox_content = [ text1 ]
   
    #Add everything into a ListBox and return it
    screen = urwid.ListBox(urwid.SimpleListWalker(listbox_content))
    return screen
    
