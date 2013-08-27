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
#fields = ["hostname", "domain", "mgmt_if","dhcp_start","dhcp_end",
#          "blank","ext_if","ext_dns"]
fields = ["HOSTNAME", "DNS_DOMAIN", "DNS_SEARCH","DNS_UPSTREAM",
          "ADMIN_NETWORK/interface", "ADMIN_NETWORK/first",
          "ADMIN_NETWORK/last"]
DEFAULTS = {
  "ADMIN_NETWORK/interface" : { "label"  : "Management Interface",
                   "tooltip": "This is the INTERNAL network for provisioning",
                   "value"  : "eth0"},

  "ADMIN_NETWORK/first"     : { "label"  : "DHCP Pool Start",
                   "tooltip": "Used for defining IPs for hosts and instance public addresses",
                   "value"  : "10.0.0.201"},
  "ADMIN_NETWORK/last"   : { "label"  : "DHCP Pool End",
                   "tooltip": "Used for defining IPs for hosts and instance public addresses",
                   "value"  : "10.0.0.254"},
#  "ext_if"     : { "label"  : "External Interface",
#                   "tooltip": "This is the EXTERNAL network for Internet access",
#                   "value"  : "eth1"},
  "DNS_UPSTREAM" : { "label"  : "External DNS",
                   "tooltip": "DNS server(s) (comma separated) to handle DNS\
 requests (example 8.8.8.8)",
                   "value"  : "8.8.8.8"},
  "DNS_DOMAIN"   : { "label"  : "Domain",
                   "tooltip": "Domain suffix to user for all nodes in your cluster",
                   "value"  : "example.com"},
  "DNS_SEARCH"   : { "label"  : "Search Domain",
                   "tooltip": "Domains to search when looking up DNS\
 (space separated)",
                   "value"  : "example.com"},
  "HOSTNAME"     : { "label"  : "Hostname",
                   "tooltip": "Hostname to use for Fuel master node",
                   "value"  : "fuel-pm"}
}
YAMLTREE = "cobbler_common"



class cobblerconf(urwid.WidgetWrap):
  def __init__(self, parent):
    self.name="Managed Network"
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
      if fieldname == "blank":
        pass
      else:
        responses[fieldname]=self.edits[index].get_edit_text()

    ###Validate each field
    errors=[]
    
    #hostname must be under 60 chars
    if len(responses["HOSTNAME"]) >= 60:
       errors.append("Hostname must be under 60 chars.")
    
    #hostname must not be empty
    if len(responses["HOSTNAME"]) == 0:
       errors.append("Hostname must not be empty.")

    #hostname needs to have valid chars
    if not re.match('[a-z0-9-]',responses["HOSTNAME"]):
      errors.append("Hostname must contain only alphanumeric and hyphen.")

    #domain must be under 180 chars
    if len(responses["DNS_DOMAIN"]) >= 180:
       errors.append("Domain must be under 180 chars.")
    
    #domain must not be empty
    if len(responses["DNS_DOMAIN"]) == 0:
       errors.append("Domain must not be empty.")

    #domain needs to have valid chars
    if not re.match('[a-z0-9-.]',responses["DNS_DOMAIN"]):
      errors.append("Domain must contain only alphanumeric, period and hyphen.")

    #ensure management interface is valid
    if responses["ADMIN_NETWORK/interface"] not in self.netsettings.keys():
      errors.append("Management interface not valid")
    else:
      ###Ensure pool start and end are on the same subnet as mgmt_if
      #Ensure mgmt_if has an IP first
      if len(self.netsettings[responses["ADMIN_NETWORK/interface"]]["addr"]) == 0:
        errors.append("Management interface isn't configured. Go to Interfaces\
  to configure this interface first.")
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
           errors.append("DHCP Pool start is not in the same subnet as management interface.")
         if network.inSameSubnet(responses["ADMIN_NETWORK/last"],mgmt_if_ipaddr,
                                 netmask) is False:
           errors.append("DHCP Pool end is not in the same subnet as management interface.")



    #ensure external interface is valid
    #if responses["ext_if"] not in self.netsettings.keys():
    #  errors.append("External interface not valid")

    #ensure external DNS is valid
    if len(responses["DNS_UPSTREAM"]) == 0:
      #We will allow empty if user doesn't need it
      pass
    else:
      #Validate first IP address
      try:
        if netaddr.valid_ipv4(responses["DNS_UPSTREAM"].split(",")[0]):
          DNS_UPSTREAM=netaddr.IPAddress(responses["DNS_UPSTREAM"])
        #Try to resolve with our IPs
        #from twisted.names import client
        #for nameserver in responses["ext_dns"].split(","):
        #   resolver = client.createResolver(servers=[(nameserver,53))
        #   if resolver.getHostByName('wikipedia.org')
           
        else:
           raise Exception("")
      except:
        errors.append("Not a valid IP address for External DNS: %s" 
                       % responses["DNS_UPSTREAM"])
    
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

    #Need to decide if we are pre-deployment or post-deployment
    #Always save even if "post"
    self.save(responses)
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

  def load(self):
    #Read in yaml
    oldsettings=Settings().read(self.parent.settingsfile)
    log.debug("Old settings %s" % oldsettings)
    log.debug(oldsettings.items())
    log.debug(oldsettings.keys())
    log.debug(oldsettings.values())
    for setting in DEFAULTS.keys():
        if "/" in setting:
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
      self.netsettings[iface]['mac'] = netifaces.ifaddresses(iface)[netifaces.AF_LINK][0]['addr']

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
    #condensed mode:
    self.net_text1.set_text("Interface: %s" % self.activeiface)
    self.net_text2.set_text("IP:      %-15s  MAC: %s" % (self.netsettings[self.activeiface]['addr'],
                                              self.netsettings[self.activeiface]['mac']))
    self.net_text3.set_text("Netmask: %-15s  Gateway: %s" % 
                            (self.netsettings[self.activeiface]['netmask'],
                            self.gateway))

    self.net_text4.set_text("")
    self.net_text5.set_text("")
    #spread out mode
#    self.net_text1.set_text("Current network settings for %s" % self.activeiface)
#    self.net_text2.set_text("MAC address:      %s" % self.netsettings[self.activeiface]['mac'])
#    self.net_text3.set_text("IP address:       %s" % self.netsettings[self.activeiface]['addr'])
#    self.net_text4.set_text("Netmask:          %s" % self.netsettings[self.activeiface]['netmask'])
#    self.net_text5.set_text("Default gateway:  %s" % (self.gateway))
#
  def setExtIfaceFields(self, enabled=True):
    ###TODO: Define ext iface fields as disabled and then toggle
    pass
  def screenUI(self):
    #Define your text labels, text fields, and buttons first
    text1 = urwid.Text("Enter configuration necessary for Cobbler setup.")

    #Current network settings
    self.net_text1 = TextLabel("")
    self.net_text2 = TextLabel("")
    self.net_text3 = TextLabel("")
    self.net_text4 = TextLabel("")
    self.net_text5 = TextLabel("")
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
                                 #self.net_text4, self.net_text5, 
                                 self.net_choices,blank])
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
    
