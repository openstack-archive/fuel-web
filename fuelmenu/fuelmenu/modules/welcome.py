#!/usr/bin/env python
# -*- coding: utf-8 -*-
import urwid
import urwid.raw_display
import urwid.web_display
from fuelmenu.common.urwidwrapper import *
<<<<<<< HEAD
=======


>>>>>>> 265265e6e18510422b50eba78bac1483d41e5052
blank = urwid.Divider()


class welcome():
<<<<<<< HEAD
    def __init__(self, parent):
        self.name = "Welcome"
        self.priority = 1
        self.visible = False
        self.screen = self.screenUI()

    def check(self):
        #TODO: Ensure all params are filled out and sensible
        return True

    def refresh(self):
        pass

    def screenUI(self):
        #Define your text labels, text fields, and buttons first
        text1 = urwid.Text("Welcome to Fuel! Use the menu on the left")
        fuellogo_huge = [
=======
  def __init__(self, parent):
    self.name="Welcome"
    self.priority=1
    self.visible=False
    self.screen = self.screenUI()

  def check(self):
    #TODO: Ensure all params are filled out and sensible
    return True

  def screenUI(self):
    #Define your text labels, text fields, and buttons first
    text1 = urwid.Text("Welcome to Fuel! Use the menu on the left")
    fuellogo_huge=[
>>>>>>> 265265e6e18510422b50eba78bac1483d41e5052
[('light gray','YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY')],
[('light gray','YYYY'),('red','YYYYYYYYYYYYYYYYYYYY'),('light gray','YYYYYYYYYY'),('red','YYYY'),('light gray','YYYYYYYYYYYY'),('red','YYYY'),('light gray','YYYYYYYYYYYY'),('red','YYYYYYYYYYYYYYYYYYYY'),('light gray','YYYYYYYYYY'),('red','YYYY'),('light gray','YYYYYYYYYYYYYYYYYYYY')],
[('light gray','YY'),('red','YYYYYYYYYYYYYYYYYYYYYYYY'),('light gray','YYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYYYYYYYYYYYYYYYYYY'),('light gray','YYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYY')],
[('light gray','YY'),('red','YYYYYYYYYYYYYYYYYYYYYYYY'),('light gray','YYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYYYYYYYYYYYYYYYYYY'),('light gray','YYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYY')],
[('light gray','YY'),('red','YYYYYYYYYYYYYYYYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYYYYYYYYYYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYY')],
[('light gray','YY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYY')],
[('light gray','YY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYY')],
[('light gray','YY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYY')],
[('light gray','YY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYY')],
[('light gray','YY'),('red','YYYYYYYYYYYYYYYY'),('light gray','YYYYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYYYYYYYYYY'),('light gray','YYYYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYY')],
[('light gray','YY'),('red','YYYYYYYYYYYYYYYYYY'),('light gray','YYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYYYYYYYYYYYY'),('light gray','YYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYY')],
[('light gray','YY'),('red','YYYYYYYYYYYYYYYYYY'),('light gray','YYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYYYYYYYYYYYY'),('light gray','YYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYY')],
[('light gray','YY'),('red','YYYYYYYYYYYYYYYY'),('light gray','YYYYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYYYYYYYYYY'),('light gray','YYYYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYY')],
[('light gray','YY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYY')],
[('light gray','YY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYY')],
[('light gray','YY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYY')],
[('light gray','YY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYY')],
[('light gray','YY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYYYY'),('red','YYYYYYYY'),('light gray','YYYY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYY'),('red','YYYYYYYYYYYYYYYYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYYYYYYYYYYYYYYYY'),('light gray','YYYY')],
[('light gray','YY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYYYY'),('red','YYYYYYYYYYYYYYYYYYYY'),('light gray','YYYYYYYYYY'),('red','YYYYYYYYYYYYYYYYYYYYYYYY'),('light gray','YYYYYY'),('red','YYYYYYYYYYYYYYYYYYYYYYYY'),('light gray','YY')],
[('light gray','YY'),('red','YYYYYYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYYYYYY'),('red','YYYYYYYYYYYYYYYY'),('light gray','YYYYYYYYYYYY'),('red','YYYYYYYYYYYYYYYYYYYYYYYY'),('light gray','YYYYYY'),('red','YYYYYYYYYYYYYYYYYYYYYYYY'),('light gray','YY')],
[('light gray','YYYY'),('red','YYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYYYYYYYYYY'),('red','YYYYYYYYYYYY'),('light gray','YYYYYYYYYYYYYYYY'),('red','YYYYYYYYYYYYYYYYYYYY'),('light gray','YYYYYYYY'),('red','YYYYYYYYYYYYYYYYYYYYYY'),('light gray','YYYY')],
[('light gray','YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY')],
[('light gray','YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY')],
[('light gray','YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY')],
[('light gray','YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY')],
[('light gray','YYYYYY'),('black','YYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYYYYYY'),('black','YYYYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY'),('black','YYYYYY'),('light gray','YYYYYYYYYYYYYYYYYYYYYYYYYY'),('black','YY'),('light gray','YYYYYYYY')],
[('light gray','YYYY'),('black','YY'),('light gray','YYYYYYYYYYYYYYYYYYYYYYYYYYYY'),('black','YY'),('light gray','YYYYYY'),('black','YY'),('light gray','YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY'),('black','YY'),('light gray','YYYYYYYY'),('black','YY'),('light gray','YYYYYYYYYYYYYYYYYYYYYY'),('black','YY'),('light gray','YYYYYYYY')],
[('light gray','YY'),('black','YYYYYY'),('light gray','YYYY'),('black','YYYY'),('light gray','YYYY'),('black','YYYY'),('light gray','YYYYYYYYYY'),('black','YY'),('light gray','YYYYYY'),('black','YY'),('light gray','YY'),('black','YYYYYY'),('light gray','YYYYYY'),('black','YYYY'),('light gray','YYYY'),('black','YYYYYY'),('light gray','YYYY'),('black','YY'),('light gray','YYYYYY'),('black','YYYYYY'),('light gray','YY'),('black','YYYYYY'),('light gray','YYYYYY'),('black','YYYY'),('light gray','YY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YY')],
[('light gray','YYYY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YY'),('black','YY'),('light gray','YYYYYYYYYYYY'),('black','YY'),('light gray','YYYYYY'),('black','YY'),('light gray','YY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YYYYYY'),('black','YY'),('light gray','YYYYYYYYYY'),('black','YY'),('light gray','YY'),('black','YY'),('light gray','YYYYYY'),('black','YY'),('light gray','YY'),('black','YY'),('light gray','YYYY')],
[('light gray','YYYY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YY'),('black','YY'),('light gray','YYYYYYYYYYYY'),('black','YY'),('light gray','YYYYYY'),('black','YY'),('light gray','YY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YY'),('black','YYYYYYYY'),('light gray','YY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YYYYYY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YYYYYY'),('black','YYYYYY'),('light gray','YY'),('black','YY'),('light gray','YYYYYY'),('black','YYYY'),('light gray','YYYYYY')],
[('light gray','YYYY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YY'),('black','YY'),('light gray','YYYYYYYYYYYY'),('black','YY'),('light gray','YYYYYY'),('black','YY'),('light gray','YY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YY'),('black','YY'),('light gray','YYYYYYYY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YYYYYYYY'),('black','YY'),('light gray','YY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YY'),('black','YY'),('light gray','YYYYYY'),('black','YY'),('light gray','YY'),('black','YY'),('light gray','YYYY')],
[('light gray','YYYY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YY'),('black','YY'),('light gray','YYYYYYYYYYYY'),('black','YY'),('light gray','YYYYYY'),('black','YY'),('light gray','YY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YY'),('black','YY'),('light gray','YYYYYYYY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YYYYYYYY'),('black','YY'),('light gray','YY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YY'),('black','YY'),('light gray','YYYYYY'),('black','YY'),('light gray','YY'),('black','YY'),('light gray','YYYY')],
[('light gray','YYYY'),('black','YY'),('light gray','YYYYYY'),('black','YYYY'),('light gray','YYYY'),('black','YY'),('light gray','YYYYYYYYYYYYYY'),('black','YYYYYY'),('light gray','YYYY'),('black','YYYYYY'),('light gray','YYYYYY'),('black','YYYYYY'),('light gray','YY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YY'),('black','YYYYYY'),('light gray','YYYYYY'),('black','YY'),('light gray','YYYY'),('black','YYYYYY'),('light gray','YYYY'),('black','YYYY'),('light gray','YY'),('black','YY'),('light gray','YYYY'),('black','YY'),('light gray','YY')],
[('light gray','YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY'),('black','YY'),('light gray','YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY')],
[('light gray','YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY'),('black','YY'),('light gray','YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY')],
[('light gray','YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY')],
]
<<<<<<< HEAD
        fuellogo_small=[
[('red',u'±ÛÛÛÛÛÛÛÛÛÛ±  ±ÛÛ±     ±ÛÛ±    ±ÛÛÛÛÛÛÛÛÛ±   ±ÛÛ±     TM')],
=======
    fuellogo_small=[  
[('red',u'±ÛÛÛÛÛÛÛÛÛÛ±  ±ÛÛ±     ±ÛÛ±    ±ÛÛÛÛÛÛÛÛÛ±   ±ÛÛ±     TM')],                              
>>>>>>> 265265e6e18510422b50eba78bac1483d41e5052
[('red',u'Û²²²²²²²²²²Û  Û²²²     Û²²²    Û²²²²²²²²²²   Û²²²')],
[('red',u'Û²²²²²²²²²²°  Û²²²     Û²²²    Û²²²²²²²²²±   Û²²²')],
#[('red',u'Û²²²          Û²²²     Û²²²    Û²²²          Û²²²')],
#[('red',u'Û²²²          Û²²²     Û²²²    Û²²²          Û²²²')],
[('red',u'Û²²²          Û²²²     Û²²²    Û²²²          Û²²²')],
[('red',u'Û²²²          Û²²²     Û²²²    Û²²²          Û²²²')],
[('red',u'Û²²²ÛÛÛÛÛ     Û²²²     Û²²²    Û²²²ÛÛÛÛÛ     Û²²²')],
[('red',u'Û²²²²²²²²     Û²²²     Û²²²    Û²²²²²²²²     Û²²²')],
#[('red',u'Û²²²          Û²²²     Û²²²    Û²²²          Û²²²')],
#[('red',u'Û²²²          Û²²²     Û²²²    Û²²²          Û²²²')],
[('red',u'Û²²²          Û²²²     Û²²²    Û²²²          Û²²²')],
[('red',u'Û²²²          Û²²²Û   Û²²²²    Û²²²          Û²²²')],
[('red',u'Û²²²          ±²²²²ÛÛÛ²²²²°    Û²²²ÛÛÛÛÛÛ°   Û²²²ÛÛÛÛÛÛÛ°')],
[('red',u'Û²²²           ²²²²²²²²²²²     Û²²²²²²²²²Û   Û²²²²²²²²²²Û')],
[('red',u'±²²°            °²²²²²²²°      ±²²²²²²²²²°   ±²²²²²²²²²²°')],
#[''],
#[''],
[('light gray',u'  ÛÛ           ÛÛÛ                  ÛÛÛ              Û  R')],
[('light gray',u' Û            Û   Û                Û     Û           Û   ')],
[('light gray',u'ÛÛÛ  ÛÛ  ÛÛÛ  Û   Û ÛÛÛ  ÛÛÛÛ ÛÛÛÛ Û    ÛÛÛ  ÛÛ   ÛÛ Û  Û')],
[('light gray',u' Û  Û  Û Û    Û   Û Û  Û Û  Û Û  Û  ÛÛ   Û     Û Û   Û Û')],
[('light gray',u' Û  Û  Û Û    Û   Û Û  Û ÛÛÛÛ Û  Û    Û  Û   ÛÛÛ Û   ÛÛ')],
[('light gray',u' Û  Û  Û Û    Û   Û Û  Û Û    Û  Û    Û  Û  Û  Û Û   Û Û')],
[('light gray',u' Û   ÛÛ  Û     ÛÛÛ  ÛÛÛ  ÛÛÛÛ Û  Û ÛÛÛ   ÛÛ  ÛÛÛ  ÛÛ Û  Û')],
[('light gray',u'                     Û')],
[('light gray',u'                     Û')],
]
<<<<<<< HEAD
        logotexts=[]
        for line in fuellogo_small:
            logotexts.append(TextLabel(line))
        #Build all of these into a list
        listbox_content = [ text1 ] + logotexts

        #Add everything into a ListBox and return it
        screen = urwid.ListBox(urwid.SimpleListWalker(listbox_content))
        return screen
=======
    logotexts=[]
    for line in fuellogo_small:
       logotexts.append(TextLabel(line))
    #Build all of these into a list
    listbox_content = [ text1 ] + logotexts
   
    #Add everything into a ListBox and return it
    screen = urwid.ListBox(urwid.SimpleListWalker(listbox_content))
    return screen
    
>>>>>>> 265265e6e18510422b50eba78bac1483d41e5052
