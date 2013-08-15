#!/usr/bin/env python

import urwid
import urwid.raw_display
import urwid.web_display
import logging
import sys
import copy
sys.path.append("/home/mmosesohn/git/fuel/iso/fuelmenu")
from settings import *
from urwidwrapper import *
log = logging.getLogger('fuelmenu.mirrors')
log.info("test")
blank = urwid.Divider()

DEFAULTS = {
"custom_mirror" : "http://mirror.your-company-name.com/",
"parent_proxy"  : "",
"port"          : "3128"
}

class mirrors(urwid.WidgetWrap):
  def __init__(self, parent):
    self.name="Repo Mirrors"
    self.priority=25
    self.visible=True
    self.parent = parent
    self.listbox_content = []
    self.settings = copy.deepcopy(DEFAULTS)
    self.screen = self.screenUI()

  def apply(self, args):
    if not self.check(args):
        log.error("Check failed. Not applying")
        return False
    conf = Settings()
    conf.write(module="mirrors",values=self.settings)
    
  def check(self, args):
    log = logging.getLogger('fuelmenu.mirrors')
    
    customurl = self.edit1.get_edit_text()
    self.parent.footer.set_text("Checking %s" % customurl)
    log.info("Checking %s" % customurl)
    if self.repochoice == "Defult":
      self.parent.footer.set_text("")
      pass
    else:
      #Ensure host can connect
      import subprocess
      reachable = subprocess.call(["curl","-o","/dev/null","--silent","--head","--write-out","'%{http_code}\n'",customurl])
      error_msg = None
      if reachable == 0:
         pass
      elif reachable == 1 or reachable == 3:
         error_msg = u"Unrecognized protocol. Did you spell it right?"
      elif reachable == 6:
         error_msg = u"Couldn't resolve host."
      elif reachable == 7:
         error_msg = u"Couldn't connect to host."
      elif reachable == 6:
         error_msg = u"Couldn't resolve host."
      if error_msg:
         self.parent.footer.set_text("Could not reach custom mirror. Error: %s" % (error_msg))
         return False
      self.parent.footer.set_text("Reached custom mirror!")

      #Ensure valid page with 2XX or 3XX return code
      status_code = subprocess.check_output(["curl","-o","/dev/null","--silent","--head","--write-out","'\%{http_code}'",customurl])
      import re
      regexp = re.compile(r'[23]\d\d')
      if regexp.search(status_code) is not None:
         error_msg = "URL not reachable on server. Error %s" % status_code
         log.error("Could not reach custom url %s. Error code: %s" % (customurl, reachable))
         self.parent.footer.set_text("Could not reach custom url %s. Error code: %s" % (customurl, reachable))
         return False

    self.parent.footer.set_text("Repo mirror OK!")
    return True

  def radioSelect(self, current, state, user_data=None):
    for rb in current.group:
       if rb.get_label() == current.get_label():
         continue
       if rb.base_widget.state == True:
         self.repochoice = rb.base_widget.get_label()
         break

  #def keypress(self, size, key):
  #  self.parent.footer.set_text("keypress")
  #def displayTooltip(self, obj):
  #  focus = obj.get_focus()[0].content
  #  self.parent.footer.set_text(focus.get_label())

  def screenUI(self):
    #Define your text labels, text fields, and buttons first
    text1 = TextLabel(u"Choose repo mirrors to use.\n"
     u"Note: Refer to Fuel documentation on how to set up a custom mirror.")
    choice_list = [u"Default", u"Custom"]
    self.choices = ChoicesGroup(self, choice_list)
    self.repochoice = "Default"
    #self.edit1 = TextField("custom_mirror", "Custom URL:", 15, DEFAULTS["custom_mirror"], "URL goes here", self.parent.footer)
    self.edit1 = TextField("custom_mirror", "Custom URL:", 15, DEFAULTS["custom_mirror"], "URL goes here", self.parent.footer)
    self.edit2 = TextField("parent_proxy", "Squid parent proxy:", 20, DEFAULTS["parent_proxy"], "Squid proxy URL (include http://)", self.parent.footer)
    self.edit3 = TextField("port", "Port:", 5, DEFAULTS["parent_proxy"], "Squid Proxy port (usually 3128)", self.parent.footer)
    self.proxyedits = Columns([('weight', 3, self.edit2), self.edit3])

    #Button to check
    button_check = Button("Check", self.check)
    #Button to apply (and check again)
    button_apply = Button("Apply", self.apply)
    #Wrap into Columns so it doesn't expand and look ugly
    check_col = Columns([button_check, button_apply,('weight',7,blank)])
    
    #Build all of these into a list
    self.listbox_content = [ text1, blank, blank, self.choices, blank, self.edit1, blank, self.proxyedits, blank, blank, check_col ]
   
    #Add everything into a ListBox and return it
    walker = urwid.SimpleListWalker(self.listbox_content)
    #urwid.connect_signal(walker, 'modified', self.displayTooltip)
    self.myscreen = urwid.ListBox(walker)
    return self.myscreen
    
