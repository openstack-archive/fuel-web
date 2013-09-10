#!/usr/bin/env python

import urwid
import urwid.raw_display
import urwid.web_display
import logging
import sys
import re
import copy
import socket, struct
import netaddr
sys.path.append("/home/mmosesohn/git/fuel/iso/fuelmenu")
from settings import *
from common import network, puppet, replace, nailyfactersettings
from common.urwidwrapper import *
log = logging.getLogger('fuelmenu.mirrors')
log.info("test")
blank = urwid.Divider()

#Need to define fields in order so it will render correctly
#fields = ["hostname", "domain", "mgmt_if","dhcp_start","dhcp_end",
#          "blank","ext_if","ext_dns"]
fields = ["static_label", 
          "ADMIN_NETWORK/static_start", "ADMIN_NETWORK/static_end", 
          "blank", "dynamic_label", "ADMIN_NETWORK/first",
          "ADMIN_NETWORK/last"]
facter_translate = {
  "ADMIN_NETWORK/interface"    : "internal_interface",
  "ADMIN_NETWORK/interface"    : "internal_ipaddress",
  "ADMIN_NETWORK/first"        : "dhcp_pool_start",
  "ADMIN_NETWORK/last"         : "dhcp_pool_end",
  "ADMIN_NETWORK/static_start" : "dhcp_static_pool_start",
  "ADMIN_NETWORK/static_end"   : "dhcp_static_pool_end",
}
mnbs_internal_ipaddress="10.20.0.2"
mnbs_internal_netmask="255.255.255.0"
mnbs_static_pool_start="10.20.0.130"
mnbs_static_pool_end="10.20.0.250"
mnbs_dhcp_pool_start="10.20.0.10"
mnbs_dhcp_pool_end="10.20.0.120"
mnbs_internal_interface="eth1"

DEFAULTS = {
  #"ADMIN_NETWORK/interface" : { "label"  : "Management Interface",
  #                 "tooltip": "This is the INTERNAL network for provisioning",
  #                 "value"  : "eth0"},
  "ADMIN_NETWORK/first"     : { "label"  : "DHCP Pool Start",
                   "tooltip": "Used for defining IPs for hosts and instance public addresses",
                   "value"  : "10.0.0.130"},
  "ADMIN_NETWORK/last"   : { "label"  : "DHCP Pool End",
                   "tooltip": "Used for defining IPs for hosts and instance public addresses",
                   "value"  : "10.0.0.254"},
  "static_label"            : { "label"  : "Static pool for installed nodes:",
                   "tooltip" : "",
                   "value"  : "label"},
  "ADMIN_NETWORK/static_start" : { "label"  : "Static Pool Start",
                   "tooltip": "Static pool for installed nodes",
                   "value"  : "10.0.0.10"},
  "ADMIN_NETWORK/static_end": { "label"  : "Static Pool End",
                   "tooltip": "Static pool for installed nodes",
                   "value"  : "10.0.0.120"},
  "dynamic_label"            : { "label"  : "DHCP pool for node discovery:",
                   "tooltip" : "",
                   "value"  : "label"},
  #"ADMIN_NETWORK/dynamic_start" : { "label"  : "Static Pool Start",
  #                 "tooltip": "DHCP pool for node discovery",
  #                 "value"  : "10.0.0.10"},
  #"ADMIN_NETWORK/dynamic_end": { "label"  : "Static Pool End",
  #                 "tooltip": "DHCP pool for node discovery",
  #                 "value"  : "10.0.0.120"},
}

class cobblerconf(urwid.WidgetWrap):
  def __init__(self, parent):
    self.name="PXE Setup"
    self.priority=20
    self.visible=True
    self.netsettings = dict()
    self.deployment="pre"
    self.getNetwork()
    self.gateway=self.get_default_gateway_linux()
    self.activeiface = sorted(self.netsettings.keys())[0]
    self.extdhcp=True
    self.parent = parent
    self.oldsettings= self.load()
    self.screen = self.screenUI()
     
  def check(self, args):
    """Validates that all fields have valid values and some sanity checks"""
    #Get field information
    responses=dict()

    for index, fieldname in enumerate(fields):
      if fieldname == "blank" or "label" in fieldname:
        pass
      else:
        responses[fieldname]=self.edits[index].get_edit_text()

    ###Validate each field
    errors=[]
    
    #ensure management interface is valid
    if responses["ADMIN_NETWORK/interface"] not in self.netsettings.keys():
      errors.append("Management interface not valid")
    else:
      ###Ensure pool start and end are on the same subnet as mgmt_if
      #Ensure mgmt_if has an IP first
      if len(self.netsettings[responses["ADMIN_NETWORK/interface"]]["addr"]) == 0:
        errors.append("Go to Interfaces to configure management interface first.")
      else:
         #Ensure ADMIN_NETWORK/interface is not running DHCP
         if self.netsettings[responses["ADMIN_NETWORK/interface"]]["bootproto"] == "dhcp":
           errors.append("Management interface is configured for DHCP. Go to Interfaces\
  to configure this interface to be static first.")
  
         #Ensure DHCP Pool Start and DHCP Pool are valid IPs
         try:
           if netaddr.valid_ipv4(responses["ADMIN_NETWORK/first"]):
             dhcp_start=netaddr.IPAddress(responses["ADMIN_NETWORK/first"])
           else:
             raise Exception("")
         except Exception, e:
           errors.append("Not a valid IP address for DHCP Pool Start: %s" 
                         % e)
                         #% responses["ADMIN_NETWORK/first"])
         try:
           if netaddr.valid_ipv4(responses["ADMIN_NETWORK/last"]):
             dhcp_end=netaddr.IPAddress(responses["ADMIN_NETWORK/last"])
           else:
             raise Exception("")
         except:
           errors.append("Not a valid IP address for DHCP Pool end: %s" 
                         % responses["ADMIN_NETWORK/last"])
  
         #Ensure pool start and end are in the same subnet of each other
         netmask=self.netsettings[responses["ADMIN_NETWORK/interface"]]["netmask"]
         if network.inSameSubnet(responses["ADMIN_NETWORK/first"],responses["ADMIN_NETWORK/last"],
                                 netmask) is False:
           errors.append("DHCP Pool start and end are not in the same subnet.")
  
         #Ensure pool start and end are in the netmask of ADMIN_NETWORK/interface
         mgmt_if_ipaddr=self.netsettings[responses["ADMIN_NETWORK/interface"]]["addr"]
         if network.inSameSubnet(responses["ADMIN_NETWORK/first"],mgmt_if_ipaddr,
                                 netmask) is False:
           errors.append("DHCP Pool start does not match management network.")
         if network.inSameSubnet(responses["ADMIN_NETWORK/last"],mgmt_if_ipaddr,
                                 netmask) is False:
           errors.append("DHCP Pool end is not in the same subnet as management interface.")

    if len(errors) > 0:
      self.parent.footer.set_text("Errors: %s First error: %s" % (len(errors), errors[0]))
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

    #Always save even if "post"
    self.save(responses)
    #Need to decide if we are pre-deployment or post-deployment
    if self.deployment == "post":
      self.updateCobbler(responses)
      services.restart("cobbler")
  
  def updateCobbler(self, params):  
    patterns={
      'cblr_server'      : '^server: .*',
      'cblr_next_server' : '^next_server: .*',
      'mgmt_if'     : '^interface=.*',
      'domain'      : '^domain=.*',
      'server'      : '^server=.*',
      'dhcp-range'  : '^dhcp-range=',
      'dhcp-option' : '^dhcp-option=',
      'pxe-service' : '^pxe-service=(^,)',
      'dhcp-boot'   : '^dhcp-boot=([^,],{3}),'
      }
  def cancel(self, button):
    for index, fieldname in enumerate(fields):
      if fieldname == "blank" or "label" in fieldname:
        pass
      else:
        self.edits[index].set_edit_text(DEFAULTS[fieldname]['value'])

  def load(self):
    #Read in yaml
    oldsettings=Settings().read(self.parent.settingsfile)
    log.debug("Old settings %s" % oldsettings)
    log.debug(oldsettings.items())
    log.debug(oldsettings.keys())
    log.debug(oldsettings.values())
    for setting in DEFAULTS.keys():
        if "label" in setting:
           continue
        elif "/" in setting:
           part1, part2 = setting.split("/")
           DEFAULTS[setting]["value"] = oldsettings[part1][part2]
        else:
           DEFAULTS[setting]["value"] = oldsettings[setting]
    return oldsettings 
  def save(self, responses):
    ## Generic settings start ##
    newsettings = dict()
    for setting in responses.keys():
      if "/" in setting:
        part1, part2 = setting.split("/")
        if not newsettings.has_key(part1):
          #We may not touch all settings, so copy oldsettings first
          newsettings[part1]=self.oldsettings[part1]
        newsettings[part1][part2] = responses[setting]
      else:
        newsettings[setting] = responses[setting]
    ## Generic settings end ##

    ## Need to calculate and set cidr, netmask, size
    newsettings['ADMIN_NETWORK']['netmask'] = \
        self.netsettings[newsettings['ADMIN_NETWORK']['interface']]["netmask"]
    newsettings['ADMIN_NETWORK']['cidr'] = network.getCidr(
        self.netsettings[newsettings['ADMIN_NETWORK']['interface']]["addr"],
        newsettings['ADMIN_NETWORK']['netmask'])
    newsettings['ADMIN_NETWORK']['size']=network.getCidrSize(
        newsettings['ADMIN_NETWORK']['cidr'])
    

    log.debug(str(newsettings))
    Settings().write(newsettings,defaultsfile=self.parent.settingsfile,
                     outfn="newsettings.yaml")
    #Write naily.facts
    factsettings=dict()
    for key in newsettings.keys():
      factsettings[key]=newsettings[key]
    n=nailyfactersettings.NailyFacterSettings()
    n.write(factsettings)
    
    #Set oldsettings to reflect new settings
    self.oldsettings = newsettings
    #Update DEFAULTS
    for index, fieldname in enumerate(fields):
      DEFAULTS[fieldname]['value']= newsettings[fieldname]
    
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
    if dhclient_running == 0:
      return True
    else:
      return False

  
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
    if self.netsettings[self.activeiface]['link'].upper() == "UP":
       if self.netsettings[self.activeiface]['bootproto'] == "dhcp":
         self.net_text4.set_text("WARNING: Cannot run on interface with DHCP.")
       else:
         self.net_text4.set_text("")
    else:
      self.net_text4.set_text("WARNING: This interface is DOWN. Configure it first.")
  
    #Calculate and set Static/DHCP pool fields
    #Max IPs = net size - 2 (master node + bcast)
    net_ip_list = network.getNetwork(self.netsettings[self.activeiface]['addr'],
                                  self.netsettings[self.activeiface]['netmask'])
    log.debug(net_ip_list)
    try:
      half = int(len(net_ip_list)/2)
      static_pool = list(net_ip_list[:half])
      dhcp_pool = list(net_ip_list[half+1:])
      static_start = str(static_pool[0])
      static_end = str(static_pool[-1])
      dynamic_start = str(dhcp_pool[0])
      dynamic_end = str(dhcp_pool[-1])
      self.net_text4.set_text("This network configuration can support %s \
nodes." % len(dhcp_pool))
    except:
      #We don't have valid values, so mark all fields empty
      static_start = ""
      static_end = ""
      dynamic_start = ""
      dynamic_end = ""
    for index, key in enumerate(fields):
      if key == "ADMIN_NETWORK/static_start":
        self.edits[index].set_edit_text(static_start)
      elif key == "ADMIN_NETWORK/static_end":
        self.edits[index].set_edit_text(static_end)
      elif key == "ADMIN_NETWORK/first":
        self.edits[index].set_edit_text(dynamic_start)
      elif key == "ADMIN_NETWORK/last":
        self.edits[index].set_edit_text(dynamic_end)
   

  #def setExtIfaceFields(self, enabled=True):
  #  ###TODO: Define ext iface fields as disabled and then toggle
  #  pass
  def screenUI(self):
    #Define your text labels, text fields, and buttons first
    text1 = urwid.Text("Settings for PXE booting of slave nodes.")
    text2 = urwid.Text("Select the interface where PXE will run:")
    #Current network settings
    self.net_text1 = TextLabel("")
    self.net_text2 = TextLabel("")
    self.net_text3 = TextLabel("")
    self.net_text4 = TextLabel("")
    self.net_choices = ChoicesGroup(self, sorted(self.netsettings.keys()), fn=self.radioSelectIface)

    self.edits = []
    toolbar = self.parent.footer
    for key in fields:
    #for key, values in DEFAULTS.items():
       #Example: key = hostname, label = Hostname, value = fuel-pm
       if key == "blank":
         self.edits.append(blank)
       elif DEFAULTS[key]["value"] == "radio":
         label = TextLabel(DEFAULTS[key]["label"])
         choices = ChoicesGroup(self,["Yes", "No"],
                    default_value="Yes", fn=self.radioSelectExtIf)
         self.edits.append(Columns([label,choices]))
       elif DEFAULTS[key]["value"] == "label":
         self.edits.append(TextLabel(DEFAULTS[key]["label"]))
       else:
         caption = DEFAULTS[key]["label"]
         default = DEFAULTS[key]["value"]
         tooltip = DEFAULTS[key]["tooltip"]
         self.edits.append(TextField(key, caption, 23, default, tooltip, toolbar))


    #Button to check
    button_check = Button("Check", self.check)
    #Button to revert to previously saved settings
    button_cancel = Button("Cancel", self.cancel)
    #Button to apply (and check again)
    button_apply = Button("Apply", self.apply)

    #Wrap buttons into Columns so it doesn't expand and look ugly
    check_col = Columns([button_check, button_cancel,
                         button_apply,('weight',2,blank)])

    self.listbox_content = [text1, blank, text2]
    self.listbox_content.extend([self.net_choices, self.net_text1, 
                                 self.net_text2, self.net_text3, 
                                 self.net_text4, blank])
    self.listbox_content.extend(self.edits)
    self.listbox_content.append(blank)   
    self.listbox_content.append(check_col)   

    #Add listeners 
    
    #Build all of these into a list
    #self.listbox_content = [ text1, blank, blank, edit1, edit2, \
    #                    edit3, edit4, edit5, edit6, button_check ]
    self.setNetworkDetails()
   
    #Add everything into a ListBox and return it
    self.listwalker=urwid.SimpleListWalker(self.listbox_content)
    screen = urwid.ListBox(self.listwalker)
    return screen
    
