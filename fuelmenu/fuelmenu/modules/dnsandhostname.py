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
            replace.replaceInFile("/etc/hosts", expr, "%s   %s" % (
                                  managediface_ip, socket.gethostname()))

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
            msg = "If you continue without DNS, you may not be able to access \
      external data necessary for installation needed for some OpenStack \
      Releases."

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
        #Apply hostname
        expr = 'HOSTNAME=.*'
        replace.replaceInFile("/etc/sysconfig/network", expr, "HOSTNAME=%s.%s"
                              % (responses["HOSTNAME"],
                                 responses["DNS_DOMAIN"]))
        #remove old hostname from /etc/hosts
        f = open("/etc/hosts", "r")
        lines = f.readlines()
        f.close()
        with open("/etc/hosts", "w") as etchosts:
            for line in lines:
                if responses["HOSTNAME"] in line \
                        or oldsettings["HOSTNAME"] in line:
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
                "%s   %s.%s" % (managediface_ip, responses["HOSTNAME"],
                                responses['DNS_DOMAIN']))
            etchosts.close()
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
