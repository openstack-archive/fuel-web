#!/usr/bin/env python

import urwid
import urwid.raw_display
import urwid.web_display
import logging
import sys
import copy
import socket, struct
import re
import netaddr
sys.path.append("/home/mmosesohn/git/fuel/iso/fuelmenu")
from settings import *
from common import network, puppet, replace
from common.urwidwrapper import *
blank = urwid.Divider()

#Need to define fields in order so it will render correctly
fields = ["blank", "ifname", "onboot", "bootproto", "ipaddr", "netmask", "gateway"]

DEFAULTS = {
  "ifname"     : { "label"  : "Interface name:",
                   "tooltip": "Interface system identifier",
                   "value"  : "locked"},
  "onboot"     : { "label"  : "Enabled on boot:",
                   "tooltip": "",
                   "value"  : "radio"},
  "bootproto"  : { "label"  : "Configuration via DHCP:",
                   "tooltip": "",
                   "value"  : "radio",
                   "choices": ["DHCP", "Static"]},
  "ipaddr"     : { "label"  : "IP address:",
                   "tooltip": "Manual IP address (example 192.168.1.2)",
                   "value"  : ""},
  "netmask"    : { "label"  : "Netmask:",
                   "tooltip": "Manual netmask (example 255.255.255.0)",
                   "value"  : "255.255.255.0"},
  "gateway"    : { "label"  : "Default Gateway:",
                   "tooltip": "Manual gateway to access Internet (example 192.168.1.1)",
                   "value"  : ""},
}
YAMLTREE = "cobbler_common"



class interfaces(urwid.WidgetWrap):
  def __init__(self, parent):

    self.name="Network Setup"
    self.priority=5
    self.visible=True
    self.netsettings = dict()
    logging.basicConfig(filename='./fuelmenu.log',level=logging.DEBUG)
    self.log = logging
    self.log.basicConfig(filename='./fuelmenu.log',level=logging.DEBUG)
    self.log.info("init Interfaces")
    self.getNetwork()
    self.gateway=self.get_default_gateway_linux()
    self.activeiface = sorted(self.netsettings.keys())[0]
    self.extdhcp=True
    self.parent = parent
    #self.screen = self.screenUI()
     
  def check(self, args):
    """Validates that all fields have valid values and some sanity checks"""
    #Get field information
    responses=dict()
    self.parent.footer.set_text("Checking data...")
    for index, fieldname in enumerate(fields):
      if fieldname == "blank" or fieldname == "ifname":
        pass
      elif fieldname == "bootproto":
        rb_group = self.edits[index].rb_group
        if rb_group[0].state:
          responses["bootproto"]="dhcp"
        else:
          responses["bootproto"]="none"
      elif fieldname == "onboot":
        rb_group = self.edits[index].rb_group
        if rb_group[0].state:
          responses["onboot"]="yes"
        else:
          responses["onboot"]="no"
      else:
        responses[fieldname]=self.edits[index].get_edit_text()

    ###Validate each field
    errors=[]
    #Perform checks only if enabled
    if responses["onboot"] == "no":
       return responses
    #No checks yet for DHCP, just return
    if responses["bootproto"] == "dhcp":
       return responses
    #Check ipaddr, netmask, gateway only if static
    if responses["bootproto"] == "none":
       try:
         if netaddr.valid_ipv4(responses["ipaddr"]):
           ipaddr=netaddr.IPAddress(responses["ipaddr"])
         else:
           raise Exception("")
       except:
         errors.append("Not a valid IP address: %s" % responses["ipaddr"])
       try:
         if netaddr.valid_ipv4(responses["netmask"]):
           netmask=netaddr.IPAddress(responses["netmask"])
           if netmask.is_netmask is False:
             raise Exception("")
         else:
           raise Exception("")
       except:
         errors.append("Not a valid netmask: %s" % responses["netmask"])
       try:
         if len(responses["gateway"]) > 0:
           gateway=netaddr.IPAddress(responses["netmask"])
           #Check if gateway is valid
           if gateway.valid_ipv4 is False:
             raise Exception("Gateway IP address is not valid")
           #Check if gateway is in same subnet
           if network.inSameSubnet(responses["ipaddr"],responses["gateway"],
                                   responses["netmask"]) is False:
             raise Exception("Gateway IP address is not in the same subnet as\
IP address")
       except Exception, e:
         errors.append(e)
    if len(errors) > 0:
      self.parent.footer.set_text("Errors: %s First error: %s" % (len(errors), errors[0]))
      return False
    else:
      self.parent.footer.set_text("No errors found.")
      return responses

  def apply(self, args):
    responses = self.check(args)
    if responses is False:
        self.log.error("Check failed. Not applying")
        self.parent.footer.set_text("Check failed. Not applying.")
        self.log.error("%s" % (responses))
        return False

    self.parent.footer.set_text("Applying changes...")
    puppetclass="l23network::l3::ifconfig"
    if responses["onboot"].lower() == "no":
        params={"ipaddr": "none"}
    elif responses["bootproto"] == "dhcp":
        params={"ipaddr": "dhcp"}
    else:
        params={"ipaddr": responses["ipaddr"],
                "netmask": responses["netmask"]}
    if len(responses["gateway"]) > 1:
        params["gateway"]=responses["gateway"]
    self.log.info("Puppet data: %s %s %s" % (puppetclass, self.activeiface, params))    
    try:
        self.parent.refreshScreen()
        puppet.puppetApply(puppetclass,self.activeiface, params)
    except Exception, e:
        self.log.error(e)
        self.parent.footer.set_text("Error applying changes. Check logs for details.")
        self.getNetwork()
        self.setNetworkDetails()
        return False
    self.parent.footer.set_text("Changes successfully applied.")
    self.getNetwork()
    self.setNetworkDetails()

    return True

  #leftover from network. we let puppet save everything
  def save(self, args):
    newsettings = dict()
    newsettings['common'] = { YAMLTREE : { "domain" : DEFAULTS['domain']['value']}}
    for key, widget in self.edits.items():
        text = widget.original_widget.get_edit_text()
        newsettings['common'][YAMLTREE][key] = text
    log.warning(str(newsettings))
    Settings().write(newsettings, tree=YAMLTREE)
    logging.warning('And this, too')

       
  def getNetwork(self):
    """Uses netifaces module to get addr, broadcast, netmask about
       network interfaces"""
    import netifaces
    for iface in netifaces.interfaces():
      if 'lo' in iface or 'vir' in iface:
      #if 'lo' in iface or 'vir' in iface or 'vbox' in iface:
        if iface != "virbr2-nic":
          continue
      try:
        self.netsettings.update({iface: netifaces.ifaddresses(iface)[netifaces.AF_INET][0]})
        self.netsettings[iface]["onboot"]="Yes"
      except:
        #Interface is down, so mark it onboot=no
        self.netsettings.update({iface: {"addr": "", "netmask": "", 
                                         "onboot": "no"}})

      self.netsettings[iface]['mac'] = netifaces.ifaddresses(iface)[netifaces.AF_LINK][0]['addr']

      #Set link state
      try:
        with open("/sys/class/net/%s/operstate" % iface) as f:
          content = f.readlines()
          self.netsettings[iface]["link"]=content[0].strip()
      except:
        self.netsettings[iface]["link"]="unknown"
      #Change unknown link state to up if interface has an IP
      if self.netsettings[iface]["link"] == "unknown":
        if self.netsettings[iface]["addr"] != "":
          self.netsettings[iface]["link"]="up"


      #We can try to get bootproto from /etc/sysconfig/network-scripts/ifcfg-DEV
      #default to static
      self.netsettings[iface]['bootproto']="none"
      try:
        with open("/etc/sysconfig/network-scripts/ifcfg-%s" % iface) as fh:
          for line in fh:
            if re.match("^BOOTPROTO=", line):
              self.netsettings[iface]['bootproto']=line.split('=').strip()
              break
           
      except:
      #Let's try checking for dhclient process running for this interface
        if self.getDHCP(iface):
          self.netsettings[iface]['bootproto']="dhcp"
        else:
          self.netsettings[iface]['bootproto']="none"
          
    
  def getDHCP(self, iface):
    """Returns True if the interface has a dhclient process running""" 
    import subprocess
    noout=open('/dev/null','w')
    dhclient_running = subprocess.call(["pgrep","-f","dhclient.*%s" % (iface)],
                           stdout=noout, stderr=noout)
    #self.log.info("Interface %s: %s" % (iface, dhclient_running))
    if dhclient_running != 0:
        return False
    else:
        return True

  def get_default_gateway_linux(self):
    """Read the default gateway directly from /proc."""
    with open("/proc/net/route") as fh:
        for line in fh:
            fields = line.strip().split()
            if fields[1] != '00000000' or not int(fields[3], 16) & 2:
                continue

            return socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))

  def radioSelectIface(self, current, state, user_data=None):
    """Update network details and display information"""
    ### This makes no sense, but urwid returns the previous object.
    ### The previous object has True state, which is wrong.. 
    ### Somewhere in current.group a RadioButton is set to True.
    ### Our quest is to find it.
    for rb in current.group:
       if rb.get_label() == current.get_label():
         continue
       if rb.base_widget.state == True:
         self.activeiface = rb.base_widget.get_label()
         break
    self.gateway=self.get_default_gateway_linux()
    self.getNetwork()
    self.setNetworkDetails()
    return 

  def radioSelectExtIf(self, current, state, user_data=None):
    """Update network details and display information"""
    ### This makes no sense, but urwid returns the previous object.
    ### The previous object has True state, which is wrong.. 
    ### Somewhere in current.group a RadioButton is set to True.
    ### Our quest is to find it.
    for rb in current.group:
       if rb.get_label() == current.get_label():
         continue
       if rb.base_widget.state == True:
         if rb.base_widget.get_label() == "Yes":
           self.extdhcp=True
         else:
           self.extdhcp=False
         break
    self.setExtIfaceFields(self.extdhcp)
    return 

  def setNetworkDetails(self):
    #condensed mode:
    self.net_text1.set_text("Interface: %-13s  Link: %s" % (self.activeiface, self.netsettings[self.activeiface]['link'].upper()))

    self.net_text2.set_text("IP:      %-15s  MAC: %s" % (self.netsettings[self.activeiface]['addr'],
                                              self.netsettings[self.activeiface]['mac']))
    self.net_text3.set_text("Netmask: %-15s  Gateway: %s" %
                            (self.netsettings[self.activeiface]['netmask'],
                            self.gateway))
#    #Old spread out method
#    self.net_text1.set_text("Current network settings for %s" % self.activeiface)
#    self.net_text2.set_text("MAC address:      %s" % self.netsettings[self.activeiface]['mac'])
#    self.net_text3.set_text("IP address:       %s" % self.netsettings[self.activeiface]['addr'])
#    self.net_text4.set_text("Netmask:          %s" % self.netsettings[self.activeiface]['netmask'])
#    self.net_text5.set_text("Default gateway:  %s" % (self.gateway))
#
    #Set text fields to current netsettings
    for index, fieldname in enumerate(fields):
      if fieldname == "ifname":
        self.edits[index].base_widget.set_edit_text(self.activeiface)
      elif fieldname == "bootproto":
        rb_group = self.edits[index].rb_group
        for rb in rb_group:
          if self.netsettings[self.activeiface]["bootproto"].lower() == "dhcp":
            rb_group[0].set_state(True)
            rb_group[1].set_state(False)
          else:
            rb_group[0].set_state(False)
            rb_group[1].set_state(True)
      elif fieldname == "onboot":
        rb_group = self.edits[index].rb_group
        for rb in rb_group:
          if self.netsettings[self.activeiface]["onboot"].lower() == "yes":
            rb_group[0].set_state(True)
            rb_group[1].set_state(False)
          else:
            rb_group[0].set_state(False)
            rb_group[1].set_state(True)
      elif fieldname == "ipaddr":
        self.edits[index].set_edit_text(self.netsettings[self.activeiface]['addr'])
      elif fieldname == "netmask":
        self.edits[index].set_edit_text(self.netsettings[self.activeiface]['netmask'])
      elif fieldname == "gateway":
        #This is gateway for iface only if self.gateway is in same subnet
        if network.inSameSubnet(self.netsettings[self.activeiface]['addr'],
                               self.gateway,
                               self.netsettings[self.activeiface]['netmask']):
          self.edits[index].set_edit_text(self.gateway)
        else:
          self.edits[index].set_edit_text("")
  def setExtIfaceFields(self, enabled=True):
    ###TODO: Define ext iface fields as disabled and then toggle
    pass
  def screenUI(self):
    #Define your text labels, text fields, and buttons first
    text1 = TextLabel("Network interface setup")

    #Current network settings
    self.net_text1 = TextLabel("")
    self.net_text2 = TextLabel("")
    self.net_text3 = TextLabel("")
    self.net_choices = ChoicesGroup(self, sorted(self.netsettings.keys()), fn=self.radioSelectIface)

    self.edits = []
    toolbar = self.parent.footer
    for key in fields:
       #Example: key = hostname, label = Hostname, value = fuel
       if key == "blank":
         self.edits.append(blank)
       elif DEFAULTS[key]["value"] == "radio":
         label = TextLabel(DEFAULTS[key]["label"])
         if DEFAULTS[key].has_key("choices"):
           choices_list = DEFAULTS[key]["choices"]
         else:
           choices_list = ["Yes", "No"]
         choices = ChoicesGroup(self,choices_list,
                     default_value="Yes", fn=self.radioSelectExtIf)
         columns=Columns([label,choices])
         #Attach choices rb_group so we can use it later
         columns.rb_group = choices.rb_group
         self.edits.append(columns)
       else:
         caption = DEFAULTS[key]["label"]
         default = DEFAULTS[key]["value"]
         tooltip = DEFAULTS[key]["tooltip"]
         disabled = True if key == "ifname" else False
         self.edits.append(TextField(key, caption, 23, default, tooltip, 
                           toolbar, disabled=disabled))


    #Button to check
    button_check = Button("Check", self.check)
    #Button to apply (and check again)
    button_apply = Button("Apply", self.apply)

    #Wrap buttons into Columns so it doesn't expand and look ugly
    check_col = Columns([button_check, button_apply,('weight',3,blank)])

    self.listbox_content = [text1, blank]
    self.listbox_content.extend([self.net_choices, self.net_text1, 
                                 self.net_text2, self.net_text3,
                                 blank])
    self.listbox_content.extend(self.edits)
    self.listbox_content.append(blank)   
    self.listbox_content.append(check_col)   

    #Add listeners 
    
    #Build all of these into a list
    #self.listbox_content = [ text1, blank, blank, edit1, edit2, \
    #                    edit3, edit4, edit5, edit6, button_check ]
   
    #Add everything into a ListBox and return it
    self.listwalker=urwid.SimpleListWalker(self.listbox_content)
    screen = urwid.ListBox(self.listwalker)
    self.setNetworkDetails()
    return screen
    
