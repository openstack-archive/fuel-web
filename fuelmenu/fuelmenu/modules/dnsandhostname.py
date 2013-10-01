#!/usr/bin/env python

import urwid
import urwid.raw_display
import urwid.web_display
import logging
import sys
import re
import copy
import socket
import struct
import netaddr
import netifaces
import subprocess
from fuelmenu.settings import *
from fuelmenu.common import network, puppet, replace, \
    nailyfactersettings, dialog
from fuelmenu.common.urwidwrapper import *
log = logging.getLogger('fuelmenu.mirrors')
blank = urwid.Divider()

#Need to define fields in order so it will render correctly
#fields = ["hostname", "domain", "mgmt_if","dhcp_start","dhcp_end",
#          "blank","ext_if","ext_dns"]
fields = ["HOSTNAME", "DNS_DOMAIN", "DNS_SEARCH", "DNS_UPSTREAM", "blank",
          "TEST_DNS"]

DEFAULTS = {
    "HOSTNAME": {"label": "Hostname",
                 "tooltip": "Hostname to use for Fuel master node",
                 "value": socket.gethostname().split('.')[0]},
    "DNS_UPSTREAM": {"label": "External DNS",
                     "tooltip": "DNS server(s) (comma separated) to handle DNS\
 requests (example 8.8.8.8)",
                     "value": "8.8.8.8"},
    "DNS_DOMAIN": {"label": "Domain",
                   "tooltip": "Domain suffix to user for all nodes in your\
cluster",
                   "value": "domain.tld"},
    "DNS_SEARCH": {"label": "Search Domain",
                   "tooltip": "Domains to search when looking up DNS\
 (space separated)",
                   "value": "domain.tld"},
    "TEST_DNS": {"label": "Hostname to test DNS:",
                 "value": "www.google.com",
                 "tooltip": "DNS record to resolve to see if DNS is\
accessible"}
    }


class dnsandhostname(urwid.WidgetWrap):
    def __init__(self, parent):
        self.name = "DNS & Hostname"
        self.priority = 50
        self.visible = True
        self.netsettings = dict()
        self.deployment = "pre"
        self.getNetwork()
        self.gateway = self.get_default_gateway_linux()
        self.extdhcp = True
        self.parent = parent
        self.oldsettings = self.load()
        self.screen = None
        self.fixDnsmasqUpstream()
        self.fixEtcHosts()

    def fixDnsmasqUpstream(self):
        #check upstream dns server
        with open('/etc/dnsmasq.upstream', 'r') as f:
            dnslines = f.readlines()
        f.close()
        if len(dnslines) > 0:
            nameservers = dnslines[0].split(" ")[1:]
            for nameserver in nameservers:
                if not self.checkDNS(nameserver):
                    nameservers.remove(nameserver)
        else:
            nameservers = []
        if nameservers == []:
            #Write dnsmasq upstream server to default if it's not readable
            with open('/etc/dnsmasq.upstream', 'w') as f:
                nameservers = DEFAULTS['DNS_UPSTREAM'][
                    'value'].replace(',', ' ')
                f.write("nameserver %s\n" % nameservers)
                f.close()

    def fixEtcHosts(self):
        #replace ip for env variable HOSTNAME in /etc/hosts
        if self.netsettings[self.parent.managediface]["addr"] != "":
            managediface_ip = self.netsettings[
                self.parent.managediface]["addr"]
        else:
            managediface_ip = "127.0.0.1"
        found = False
        with open("/etc/hosts") as fh:
            for line in fh:
                if re.match("%s.*%s" % (managediface_ip,
                            socket.gethostname()), line):
                    found = True
                    break
        if not found:
            expr = ".*%s.*" % socket.gethostname()
            replace.replaceInFile("/etc/hosts", expr, "%s   %s %s" % (
                                  managediface_ip,
                                  socket.gethostname(),
                                  socket.gethostname().split('.')[0]))

    def fixEtcResolv(self):
        with open("/etc/resolv.conf", "w") as fh:
            fh.write("nameserver 127.0.0.1\n")
            fh.close()

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

        #hostname must be under 60 chars
        if len(responses["HOSTNAME"]) >= 60:
            errors.append("Hostname must be under 60 chars.")

        #hostname must not be empty
        if len(responses["HOSTNAME"]) == 0:
            errors.append("Hostname must not be empty.")

        #hostname needs to have valid chars
        if re.search('[^a-z0-9-]', responses["HOSTNAME"]):
            errors.append(
                "Hostname must contain only alphanumeric and hyphen.")

        #domain must be under 180 chars
        if len(responses["DNS_DOMAIN"]) >= 180:
            errors.append("Domain must be under 180 chars.")

        #domain must not be empty
        if len(responses["DNS_DOMAIN"]) == 0:
            errors.append("Domain must not be empty.")

        #domain needs to have valid chars
        if re.match('[^a-z0-9-.]', responses["DNS_DOMAIN"]):
            errors.append(
                "Domain must contain only alphanumeric, period and hyphen.")
        #ensure external DNS is valid
        if len(responses["DNS_UPSTREAM"]) == 0:
            #We will allow empty if user doesn't need external networking
            #and present a strongly worded warning
            msg = "If you continue without DNS, you may not be able to access"\
                  + " external data necessary for installation needed for " \
                  + "some OpenStack Releases."

            diag = dialog.display_dialog(
                self, TextLabel(msg), "Empty DNS Warning")

        else:
            #external DNS must contain only numbers, periods, and commas
            #TODO: More serious ip address checking
            if re.match('[^0-9.,]', responses["DNS_UPSTREAM"]):
                errors.append(
                    "External DNS must contain only IP addresses and commas.")
            #ensure test DNS name isn't empty
            if len(responses["TEST_DNS"]) == 0:
                errors.append("Test DNS must not be empty.")
            #Validate first IP address
            try:
                if netaddr.valid_ipv4(responses["DNS_UPSTREAM"].split(",")[0]):
                    DNS_UPSTREAM = responses["DNS_UPSTREAM"].split(",")[0]
                else:
                    errors.append("Not a valid IP address for External DNS: %s"
                                  % responses["DNS_UPSTREAM"])

                #Try to resolve with first address
                if not self.checkDNS(DNS_UPSTREAM):
                    errors.append("IP %s unable to resolve host."
                                  % DNS_UPSTREAM)
            except Exception, e:

                errors.append(e)
                errors.append("Not a valid IP address for External DNS: %s"
                              % responses["DNS_UPSTREAM"])

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

        self.save(responses)
        #Update network details so we write correct IP address
        self.getNetwork()
        #Apply hostname
        expr = 'HOSTNAME=.*'
        replace.replaceInFile("/etc/sysconfig/network", expr,
                              "HOSTNAME=%s.%s"
                              % (responses["HOSTNAME"],
                                 responses["DNS_DOMAIN"]))
        #remove old hostname from /etc/hosts
        f = open("/etc/hosts", "r")
        lines = f.readlines()
        f.close()
        with open("/etc/hosts", "w") as etchosts:
            for line in lines:
                if responses["HOSTNAME"] in line \
                        or self.oldsettings["HOSTNAME"] in line:
                    continue
                else:
                    etchosts.write(line)
            etchosts.close()

        #append hostname and ip address to /etc/hosts
        with open("/etc/hosts", "a") as etchosts:
            if self.netsettings[self.parent.managediface]["addr"] != "":
                managediface_ip = self.netsettings[
                    self.parent.managediface]["addr"]
            else:
                managediface_ip = "127.0.0.1"
            etchosts.write(
                "%s   %s.%s %s\n" % (managediface_ip, responses["HOSTNAME"],
                                     responses['DNS_DOMAIN'],
                                     responses["HOSTNAME"]))
            etchosts.close()
        self.fixEtcResolv()
        #Write dnsmasq upstream server
        with open('/etc/dnsmasq.upstream', 'w') as f:
            nameservers = responses['DNS_UPSTREAM'].replace(',', ' ')
            f.write("nameserver %s\n" % nameservers)
        f.close()

        ###Future feature to apply post-deployment
        #Need to decide if we are pre-deployment or post-deployment
        #if self.deployment == "post":
        #  self.updateCobbler(responses)
        #  services.restart("cobbler")

        return True
#  def updateCobbler(self, params):
#    patterns={
#      'cblr_server'      : '^server: .*',
#      'cblr_next_server' : '^next_server: .*',
#      'mgmt_if'     : '^interface=.*',
#      'domain'      : '^domain=.*',
#      'server'      : '^server=.*',
#      'dhcp-range'  : '^dhcp-range=',
#      'dhcp-option' : '^dhcp-option=',
#      'pxe-service' : '^pxe-service=(^,)',
#      'dhcp-boot'   : '^dhcp-boot=([^,],{3}),'
#      }
    def cancel(self, button):
        for index, fieldname in enumerate(fields):
            if fieldname == "blank":
                pass
            else:
                self.edits[index].set_edit_text(DEFAULTS[fieldname]['value'])

    def load(self):
        #Read in yaml
        defaultsettings = Settings().read(self.parent.defaultsettingsfile)
        oldsettings = defaultsettings
        oldsettings.update(Settings().read(self.parent.settingsfile))

        oldsettings = Settings().read(self.parent.settingsfile)
        for setting in DEFAULTS.keys():
            try:
                if "/" in setting:
                    part1, part2 = setting.split("/")
                    DEFAULTS[setting]["value"] = oldsettings[part1][part2]
                else:
                    DEFAULTS[setting]["value"] = oldsettings[setting]
            except:
                log.warning("No setting named %s found." % setting)
                continue
        #Read hostname if it's already set
        try:
            import os
            oldsettings["HOSTNAME"] = os.uname()[1]
        except:
            log.warning("Unable to look up system hostname")
        return oldsettings

    def save(self, responses):
        ## Generic settings start ##
        newsettings = dict()
        for setting in responses.keys():
            if "/" in setting:
                part1, part2 = setting.split("/")
                if part1 not in newsettings:
                #We may not touch all settings, so copy oldsettings first
                    newsettings[part1] = self.oldsettings[part1]
                newsettings[part1][part2] = responses[setting]
            else:
                newsettings[setting] = responses[setting]
        ## Generic settings end ##

        #log.debug(str(newsettings))
        Settings().write(newsettings, 
                         defaultsfile=self.parent.defaultsettingsfile,
                         outfn=self.parent.settingsfile)
        #Write naily.facts
        factsettings = dict()
        #log.debug(newsettings)
        for key in newsettings.keys():
            if key != "blank":
                factsettings[key] = newsettings[key]
        n = nailyfactersettings.NailyFacterSettings()
        n.write(factsettings)

        #Set oldsettings to reflect new settings
        self.oldsettings = newsettings
        #Update DEFAULTS
        for index, fieldname in enumerate(fields):
            if fieldname != "blank":
                DEFAULTS[fieldname]['value'] = newsettings[fieldname]

    def checkDNS(self, server):
        #Note: Python's internal resolver caches negative answers.
        #Therefore, we should call dig externally to be sure.

        noout = open('/dev/null', 'w')
        dns_works = subprocess.call(["dig", "+short", "+time=3",
                                     "+retries=1",
                                     DEFAULTS["TEST_DNS"]['value'],
                                     "@%s" % server], stdout=noout,
                                    stderr=noout)
        if dns_works != 0:
            return False
        else:
            return True

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
                self.netsettings.update({iface: netifaces.ifaddresses(
                    iface)[netifaces.AF_INET][0]})
                self.netsettings[iface]["onboot"] = "Yes"
            except:
                self.netsettings.update({iface: {"addr": "", "netmask": "",
                                                 "onboot": "no"}})
            self.netsettings[iface]['mac'] = netifaces.ifaddresses(
                iface)[netifaces.AF_LINK][0]['addr']

            #Set link state
            try:
                with open("/sys/class/net/%s/operstate" % iface) as f:
                    content = f.readlines()
                    self.netsettings[iface]["link"] = content[0].strip()
            except:
                self.netsettings[iface]["link"] = "unknown"
            #Change unknown link state to up if interface has an IP
            if self.netsettings[iface]["link"] == "unknown":
                if self.netsettings[iface]["addr"] != "":
                    self.netsettings[iface]["link"] = "up"

            #Read bootproto from /etc/sysconfig/network-scripts/ifcfg-DEV
            try:
                with open("/etc/sysconfig/network-scripts/ifcfg-%s" % iface) \
                        as fh:
                    for line in fh:
                        if re.match("^BOOTPROTO=", line):
                            self.netsettings[
                                iface]['bootproto'] = line.split('=').strip()
                            break
            except:
            #Let's try checking for dhclient process running for this interface
                if self.getDHCP(iface):
                    self.netsettings[iface]['bootproto'] = "dhcp"
                else:
                    self.netsettings[iface]['bootproto'] = "none"

    def getDHCP(self, iface):
        """Returns True if the interface has a dhclient process running"""
        import subprocess
        noout = open('/dev/null', 'w')
        dhclient_running = subprocess.call(
            ["pgrep", "-f", "dhclient.*%s" % (iface)],
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
            if rb.base_widget.state is True:
                self.activeiface = rb.base_widget.get_label()
                break
        self.gateway = self.get_default_gateway_linux()
        self.getNetwork()
        return

    def refresh(self):
        pass

    def screenUI(self):
        #Define your text labels, text fields, and buttons first
        text1 = urwid.Text("DNS and hostname setup")
        text2 = urwid.Text("Note: Leave External DNS blank if you do not have"
                           " Internet access.")

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
                self.edits.append(
                    TextField(key, caption, 23, default, tooltip, toolbar))

        #Button to check
        button_check = Button("Check", self.check)
        #Button to revert to previously saved settings
        button_cancel = Button("Cancel", self.cancel)
        #Button to apply (and check again)
        button_apply = Button("Apply", self.apply)

        #Wrap buttons into Columns so it doesn't expand and look ugly
        if self.parent.globalsave:
            check_col = Columns([button_check])
        else:
            check_col = Columns([button_check, button_cancel,
                                 button_apply, ('weight', 2, blank)])

        self.listbox_content = [text1, blank, text2, blank]
        self.listbox_content.extend(self.edits)
        self.listbox_content.append(blank)
        self.listbox_content.append(check_col)

        #Add listeners

        #Build all of these into a list
        #self.listbox_content = [ text1, blank, blank, edit1, edit2, \
        #                    edit3, edit4, edit5, edit6, button_check ]

        #Add everything into a ListBox and return it
        self.listwalker = urwid.SimpleListWalker(self.listbox_content)
        screen = urwid.ListBox(self.listwalker)
        return screen

