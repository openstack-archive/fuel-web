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
from common import network, puppet
from urwidwrapper import *
log = logging.getLogger('fuelmenu.mirrors')
log.info("test")
blank = urwid.Divider()

#Need to define fields in order so it will render correctly
fields = ["hostname", "domain", "mgmt_if","dhcp_start","dhcp_end",
          "blank","ext_if","ext_dns"]
DEFAULTS = {
  "dhcp_start" : { "label"  : "DHCP Pool Start",
                   "tooltip": "Used for defining Floating IP range",
                   "value"  : "10.0.0.201"},
  "dhcp_end"   : { "label"  : "DHCP Pool End",
                   "tooltip": "Used for defining Floating IP range",
                   "value"  : "10.0.0.254"},
  "mgmt_if"    : { "label"  : "Management Interface",
                   "tooltip": "This is the INTERNAL network for provisioning",
                   "value"  : "eth0"},
  "ext_if"     : { "label"  : "External Interface",
                   "tooltip": "This is the EXTERNAL network for Internet access",
                   "value"  : "eth1"},
  "ext_dns"    : { "label"  : "External DNS",
                   "tooltip": "DNS server(s) (comma separated) to handle DNS\
 requests (example 8.8.8.8)",
                   "value"  : "8.8.8.8"},
  "domain"     : { "label"  : "Domain",
                   "tooltip": "Domain suffix to user for all nodes in your cluster",
                   "value"  : "local"},
  "hostname"   : { "label"  : "Hostname",
                   "tooltip": "Hostname to use for Fuel master node",
                   "value"  : "fuel-pm"}
}
YAMLTREE = "cobbler_common"



class cobbler(urwid.WidgetWrap):
  def __init__(self, parent):
    self.name="Cobbler"
    self.priority=20
    self.visible=True
    self.netsettings = dict()
    self.getNetwork()
    self.gateway=self.get_default_gateway_linux()
    self.activeiface = sorted(self.netsettings.keys())[0]
    self.extdhcp=True
    self.parent = parent
    self.screen = self.screenUI()
     
  def check(self, args):
    """Validates that all fields have valid values and some sanity checks"""
    #Get field information
    responses=dict()

    for index, fieldname in enumerate(fields):
      if fieldname == "blank":
        pass
      else:
        responses[fieldname]=self.edits[index].get_edit_text()

    ###Validate each field
    errors=[]
    
    #hostname must be under 60 chars
    if len(responses["hostname"]) >= 60:
       errors.append("Hostname must be under 60 chars.")
    
    #hostname must not be empty
    if len(responses["hostname"]) == 0:
       errors.append("Hostname must not be empty.")

    #hostname needs to have valid chars
    if not re.match('[a-z0-9-]',responses["hostname"]):
      errors.append("Hostname must contain only alphanumeric and hyphen.")

    #domain must be under 180 chars
    if len(responses["domain"]) >= 180:
       errors.append("Domain must be under 180 chars.")
    
    #domain must not be empty
    if len(responses["domain"]) == 0:
       errors.append("Domain must not be empty.")

    #domain needs to have valid chars
    if not re.match('[a-z0-9-.]',responses["domain"]):
      errors.append("Domain must contain only alphanumeric, period and hyphen.")

    #ensure management interface is valid
    if responses["mgmt_if"] not in self.netsettings.keys():
      errors.append("Management interface not valid")
    else:
      ###Ensure pool start and end are on the same subnet as mgmt_if
      #Ensure mgmt_if has an IP first
      if len(self.netsettings[responses["mgmt_if"]]["addr"]) == 0:
        errors.append("Management interface isn't configured. Go to Interfaces\
  to configure this interface first.")
      else:
         #Ensure mgmt_if is not running DHCP
         if self.netsettings[responses["mgmt_if"]]["bootproto"] == "dhcp":
           errors.append("Management interface is configured for DHCP. Go to Interfaces\
  to configure this interface to be static first.")
  
         #Ensure DHCP Pool Start and DHCP Pool are valid IPs
         try:
           if netaddr.valid_ipv4(responses["dhcp_start"]):
             dhcp_start=netaddr.IPAddress(responses["dhcp_start"])
           else:
             raise Exception("")
         except Exception, e:
           errors.append("Not a valid IP address for DHCP Pool Start: %s" 
                         % e)
                         #% responses["dhcp_start"])
         try:
           if netaddr.valid_ipv4(responses["dhcp_end"]):
             dhcp_end=netaddr.IPAddress(responses["dhcp_end"])
           else:
             raise Exception("")
         except:
           errors.append("Not a valid IP address for DHCP Pool end: %s" 
                         % responses["dhcp_end"])
  
         #Ensure pool start and end are in the same subnet of each other
         netmask=self.netsettings[responses["mgmt_if"]]["netmask"]
         if network.inSameSubnet(responses["dhcp_start"],responses["dhcp_end"],
                                 netmask) is False:
           errors.append("DHCP Pool start and end are not in the same subnet.")
  
         #Ensure pool start and end are in the netmask of mgmt_if
         mgmt_if_ipaddr=self.netsettings[responses["mgmt_if"]]["addr"]
         if network.inSameSubnet(responses["dhcp_start"],mgmt_if_ipaddr,
                                 netmask) is False:
           errors.append("DHCP Pool start is not in the same subnet as management interface.")
         if network.inSameSubnet(responses["dhcp_end"],mgmt_if_ipaddr,
                                 netmask) is False:
           errors.append("DHCP Pool end is not in the same subnet as management interface.")



    #ensure external interface is valid
    if responses["ext_if"] not in self.netsettings.keys():
      errors.append("External interface not valid")

    #ensure external DNS is valid
    if len(responses["ext_dns"]) == 0:
      #We will allow empty if user doesn't need it
      pass
    else:
      #Validate first IP address
      try:
        if netaddr.valid_ipv4(responses["ext_dns"].split(",")[0]):
          ext_dns=netaddr.IPAddress(responses["ext_dns"])
        #Try to resolve with our IPs
        #from twisted.names import client
        #for nameserver in responses["ext_dns"].split(","):
        #   resolver = client.createResolver(servers=[(nameserver,53))
        #   if resolver.getHostByName('wikipedia.org')
           
        else:
           raise Exception("")
      except:
        errors.append("Not a valid IP address for External DNS: %s" 
                       % responses["ext_dns"])
    
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
        self.log.error("%s" % (responses))
        return False

  def save(self, args):
    # set up logging
    import logging
    log = logging.getLogger('fuelmenu.cobbler')
    if not self.check(args):
        log.error("Check failed. Not applying")
        return False
    responses=dict()
    for index, fieldname in enumerate(fields):
      if fieldname == "blank":
        continue
      if fieldname == "ext_dhcp":
        responses["ext_dhcp"] = self.extdhcp
        continue
      responses[fieldname]=self.edits[index].get_edit_text()


    newsettings = dict()
    newsettings['common'] = { YAMLTREE : { "domain" : DEFAULTS['domain']['value']}}
    for key, widget in self.edits.items():
        text = widget.original_widget.get_edit_text()
        newsettings['common'][YAMLTREE][key] = text
    log.warning(str(newsettings))
    Settings().write(newsettings, tree=YAMLTREE)
    logging.warning('And this, too')

       
#  def getNetwork(self):
#    """Uses netifaces module to get addr, broadcast, netmask about
#       network interfaces"""
#    import netifaces
#    for iface in netifaces.interfaces():
#      if 'lo' in iface or 'vir' in iface:
#      #if 'lo' in iface or 'vir' in iface or 'vbox' in iface:
#        continue
#      #print netifaces.ifaddresses(iface)
#      #print iface, netifaces.ifaddresses(iface)[netifaces.AF_INET][0]
#      self.netsettings.update({iface: netifaces.ifaddresses(iface)[netifaces.AF_INET][0]})
#    
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
    self.net_text1.set_text("Current network settings for %s" % self.activeiface)
    self.net_text2.set_text("IP address:       %s" % self.netsettings[self.activeiface]['addr'])
    self.net_text3.set_text("Netmask:          %s" % self.netsettings[self.activeiface]['netmask'])
    self.net_text4.set_text("Default gateway:  %s" % (self.gateway))

  def setExtIfaceFields(self, enabled=True):
    ###TODO: Define ext iface fields as disabled and then toggle
    pass
  def screenUI(self):
    #Define your text labels, text fields, and buttons first
    text1 = urwid.Text("Master node network settings")

    #Current network settings
    self.net_text1 = TextLabel("")
    self.net_text2 = TextLabel("")
    self.net_text3 = TextLabel("")
    self.net_text4 = TextLabel("")
    self.setNetworkDetails()
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
       else:
         caption = DEFAULTS[key]["label"]
         default = DEFAULTS[key]["value"]
         tooltip = DEFAULTS[key]["tooltip"]
         self.edits.append(TextField(key, caption, 23, default, tooltip, toolbar))


    #Button to check
    button_check = Button("Check", self.check)
    #Button to apply (and check again)
    button_apply = Button("Apply", self.apply)

    #Wrap buttons into Columns so it doesn't expand and look ugly
    check_col = Columns([button_check, button_apply,('weight',3,blank)])

    self.listbox_content = [text1, blank, blank]
    self.listbox_content.extend([self.net_text1, self.net_text2, self.net_text3, 
                                 self.net_text4, self.net_choices,blank])
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
    return screen
    
