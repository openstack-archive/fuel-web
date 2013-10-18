#!/usr/bin/env python
# Copyright 2013 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import dhcp_checker.api
import dhcp_checker.utils
from fuelmenu.common import dialog
from fuelmenu.common.errors import BadIPException
from fuelmenu.common import nailyfactersettings
from fuelmenu.common import network
from fuelmenu.common import timeout
import fuelmenu.common.urwidwrapper as widget
from fuelmenu.settings import Settings
import logging
import netaddr
import netifaces
import re
import socket
import struct
import subprocess
import traceback
import urwid
import urwid.raw_display
import urwid.web_display
log = logging.getLogger('fuelmenu.pxe_setup')
blank = urwid.Divider()

#Need to define fields in order so it will render correctly
fields = ["static_label",
          "ADMIN_NETWORK/static_pool_start", "ADMIN_NETWORK/static_pool_end",
          "blank", "dynamic_label", "ADMIN_NETWORK/dhcp_pool_start",
          "ADMIN_NETWORK/dhcp_pool_end"]
facter_translate = {
    "ADMIN_NETWORK/interface": "internal_interface",
    "ADMIN_NETWORK/ipaddress": "internal_ipaddress",
    "ADMIN_NETWORK/netmask": "internal_netmask",
    "ADMIN_NETWORK/dhcp_pool_start": "dhcp_pool_start",
    "ADMIN_NETWORK/dhcp_pool_end": "dhcp_pool_end",
    "ADMIN_NETWORK/static_pool_start": "static_pool_start",
    "ADMIN_NETWORK/static_pool_end": "static_pool_end",
}

DEFAULTS = {
    "ADMIN_NETWORK/dhcp_pool_start": {"label": "DHCP Pool Start",
                                      "tooltip": "Used for defining IPs for \
hosts and instance public addresses",
                                      "value": "10.0.0.130"},
    "ADMIN_NETWORK/dhcp_pool_end": {"label": "DHCP Pool End",
                                    "tooltip": "Used for defining IPs for \
hosts and instance public addresses",
                                    "value": "10.0.0.254"},
    "static_label": {"label": "Static pool for installed nodes:",
                     "tooltip": "",
                     "value": "label"},
    "ADMIN_NETWORK/static_pool_start": {"label": "Static Pool Start",
                                        "tooltip": "Static pool for installed \
nodes",
                                        "value": "10.0.0.10"},
    "ADMIN_NETWORK/static_pool_end": {"label": "Static Pool End",
                                      "tooltip": "Static pool for installed \
nodes",
                                      "value": "10.0.0.120"},
    "dynamic_label": {"label": "DHCP pool for node discovery:",
                      "tooltip": "",
                      "value": "label"},
}


class cobblerconf(urwid.WidgetWrap):
    def __init__(self, parent):
        self.name = "PXE Setup"
        self.priority = 20
        self.visible = True
        self.netsettings = dict()
        self.parent = parent
        self.deployment = "pre"
        self.getNetwork()
        self.gateway = self.get_default_gateway_linux()
        self.activeiface = sorted(self.netsettings.keys())[0]
        self.parent.managediface = self.activeiface
        self.extdhcp = True
        self.oldsettings = self.load()
        self.screen = None

    def check(self, args):
        """Validates all fields have valid values and some sanity checks."""
        self.parent.footer.set_text("Checking data...")
        self.parent.refreshScreen()

        #Refresh networking to make sure IP matches
        self.getNetwork()

        #Get field information
        responses = dict()

        for index, fieldname in enumerate(fields):
            if fieldname == "blank" or "label" in fieldname:
                pass
            else:
                responses[fieldname] = self.edits[index].get_edit_text()

        ###Validate each field
        errors = []

        #Set internal_{ipaddress,netmask,interface}
        responses["ADMIN_NETWORK/interface"] = self.activeiface
        responses["ADMIN_NETWORK/netmask"] = self.netsettings[
            self.activeiface]["netmask"]
        responses["ADMIN_NETWORK/ipaddress"] = self.netsettings[
            self.activeiface]["addr"]

        #ensure management interface is valid
        if responses["ADMIN_NETWORK/interface"] not in self.netsettings.keys():
            errors.append("Management interface not valid")
        else:
            self.parent.footer.set_text("Scanning for DHCP servers. \
Please wait...")
            self.parent.refreshScreen()

            ###Start DHCP check on this interface
            #dhcp_server_data=[{'server_id': '192.168.200.2', 'iface': 'eth2',
            #                   'yiaddr': '192.168.200.15', 'mac':
            #                '52:54:00:12:35:02', 'server_ip': '192.168.200.2',
            #                   'dport': 67, 'message': 'offer',
            #                   'gateway': '0.0.0.0'}]
            try:
                dhcptimeout = 5
                with timeout.run_with_timeout(dhcp_checker.utils.IfaceState,
                                              [self.activeiface],
                                              timeout=dhcptimeout) as iface:
                    dhcp_server_data = timeout.run_with_timeout(
                        dhcp_checker.api.check_dhcp_on_eth,
                        [iface, dhcptimeout], timeout=dhcptimeout)
            except (KeyboardInterrupt, timeout.TimeoutError):
                log.debug("DHCP scan timed out")
                log.warning(traceback.format_exc())
                dhcp_server_data = []

            num_dhcp = len(dhcp_server_data)
            if num_dhcp == 0:
                log.debug("No DHCP servers found")
            else:
                #Problem exists, but permit user to continue
                log.error("%s foreign DHCP server(s) found: %s" %
                          (num_dhcp, dhcp_server_data))

                #Build dialog elements
                dhcp_info = []
                dhcp_info.append(urwid.Padding(
                                 urwid.Text(("header", "!!! WARNING !!!")),
                                 "center"))
                dhcp_info.append(widget.TextLabel("You have selected an \
interface that contains one or more DHCP servers. This will impact \
provisioning. You should disable these DHCP servers before you continue, or \
else deployment will likely fail."))
                dhcp_info.append(widget.TextLabel(""))
                for index, dhcp_server in enumerate(dhcp_server_data):
                    dhcp_info.append(widget.TextLabel("DHCP Server #%s:" %
                                     (index + 1)))
                    dhcp_info.append(widget.TextLabel("IP address: %-10s" %
                                     dhcp_server['server_ip']))
                    dhcp_info.append(widget.TextLabel("MAC address: %-10s" %
                                     dhcp_server['mac']))
                    dhcp_info.append(widget.TextLabel(""))
                dialog.display_dialog(self, urwid.Pile(dhcp_info),
                                      "DHCP Servers Found on %s"
                                      % self.activeiface)
            ###Ensure pool start and end are on the same subnet as mgmt_if
            #Ensure mgmt_if has an IP first
            if len(self.netsettings[responses[
               "ADMIN_NETWORK/interface"]]["addr"]) == 0:
                errors.append("Go to Interfaces to configure management \
interface first.")
            else:
                #Ensure ADMIN_NETWORK/interface is not running DHCP
                if self.netsettings[responses[
                        "ADMIN_NETWORK/interface"]]["bootproto"] == "dhcp":
                    errors.append("%s is running DHCP.Change it to static "
                                  "first." % self.activeiface)

                #Ensure Static Pool Start and Static Pool are valid IPs
                try:
                    if netaddr.valid_ipv4(responses[
                            "ADMIN_NETWORK/static_pool_start"]):
                        static_start = netaddr.IPAddress(responses[
                            "ADMIN_NETWORK/static_pool_start"])
                        if not static_start:
                            raise BadIPException("Not a valid IP address")
                    else:
                        raise BadIPException("Not a valid IP address")
                except Exception:
                    errors.append("Not a valid IP address for Static Pool "
                                  "Start")
                try:
                    if netaddr.valid_ipv4(responses[
                            "ADMIN_NETWORK/static_pool_end"]):
                        static_end = netaddr.IPAddress(responses[
                            "ADMIN_NETWORK/static_pool_end"])
                        if not static_end:
                            raise BadIPException("Not a valid IP address")
                    else:
                        raise BadIPException("Not a valid IP address")
                except Exception:
                    errors.append("Invalid IP address for Static Pool End")
                #Ensure DHCP Pool Start and DHCP Pool are valid IPs
                try:
                    if netaddr.valid_ipv4(responses[
                                          "ADMIN_NETWORK/dhcp_pool_start"]):
                        dhcp_start = netaddr.IPAddress(
                            responses["ADMIN_NETWORK/dhcp_pool_start"])
                        if not dhcp_start:
                            raise BadIPException("Not a valid IP address")
                    else:
                        raise BadIPException("Not a valid IP address")
                except Exception:
                    errors.append("Invalid IP address for DHCP Pool Start")
                try:
                    if netaddr.valid_ipv4(responses[
                            "ADMIN_NETWORK/dhcp_pool_end"]):
                        dhcp_end = netaddr.IPAddress(
                            responses["ADMIN_NETWORK/dhcp_pool_end"])
                        if not dhcp_end:
                            raise BadIPException("Not a valid IP address")
                    else:
                        raise BadIPException("Not a valid IP address")
                except Exception:
                    errors.append("Invalid IP address for DHCP Pool end")

                #Ensure pool start and end are in the same subnet of each other
                netmask = self.netsettings[responses[
                                           "ADMIN_NETWORK/interface"
                                           ]]["netmask"]
                if not network.inSameSubnet(
                        responses["ADMIN_NETWORK/dhcp_pool_start"],
                        responses["ADMIN_NETWORK/dhcp_pool_end"], netmask):
                    errors.append("DHCP Pool start and end are not in the "
                                  "same subnet.")

                #Ensure pool start and end are in the right netmask
                mgmt_if_ipaddr = self.netsettings[responses[
                    "ADMIN_NETWORK/interface"]]["addr"]
                if network.inSameSubnet(responses[
                                        "ADMIN_NETWORK/static_pool_start"],
                                        mgmt_if_ipaddr, netmask) is False:
                    errors.append("Static Pool start does not match management"
                                  " network.")
                if network.inSameSubnet(responses[
                                        "ADMIN_NETWORK/static_pool_end"],
                                        mgmt_if_ipaddr, netmask) is False:
                    errors.append("Static Pool end does not match management "
                                  "network.")
                if network.inSameSubnet(responses[
                                        "ADMIN_NETWORK/dhcp_pool_start"],
                                        mgmt_if_ipaddr, netmask) is False:
                    errors.append("DHCP Pool start does not match management"
                                  " network.")
                if network.inSameSubnet(responses[
                                        "ADMIN_NETWORK/dhcp_pool_end"],
                                        mgmt_if_ipaddr, netmask) is False:
                    errors.append("DHCP Pool end does not match management "
                                  "network.")

        if len(errors) > 0:
            self.parent.footer.set_text("Error %s" % (errors[0]))
            log.error("Errors: %s %s" % (len(errors), errors))
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
        return True

    def updateCobbler(self, params):
#        patterns = \
#            {
#                'cblr_server': '^server: .*',
#                'cblr_next_server': '^next_server: .*',
#                'mgmt_if': '^interface=.*',
#                'domain': '^domain=.*',
#                'server': '^server=.*',
#                'dhcp-range': '^dhcp-range=',
#                'dhcp-option': '^dhcp-option=',
#                'pxe-service': '^pxe-service=(^,)',
#                'dhcp-boot': '^dhcp-boot=([^,],{3}),'
#            }
        pass

    def cancel(self, button):
        for index, fieldname in enumerate(fields):
            if fieldname == "blank" or "label" in fieldname:
                pass
            else:
                self.edits[index].set_edit_text(DEFAULTS[fieldname]['value'])
        self.setNetworkDetails()

    def load(self):
        #Read in yaml
        defaultsettings = Settings().read(self.parent.defaultsettingsfile)
        oldsettings = defaultsettings.copy()
        oldsettings.update(Settings().read(self.parent.settingsfile))
        log.debug("Old settings %s" % oldsettings)
        for setting in DEFAULTS.keys():
            if "label" in setting:
                continue
            elif "/" in setting:
                part1, part2 = setting.split("/")
                DEFAULTS[setting]["value"] = oldsettings[part1][part2]
            else:
                DEFAULTS[setting]["value"] = oldsettings[setting]
        if oldsettings["ADMIN_NETWORK"]["interface"] \
                in self.netsettings.keys():
            self.activeiface = oldsettings["ADMIN_NETWORK"]["interface"]
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

        ## Need to calculate and set cidr, netmask, size
        newsettings['ADMIN_NETWORK']['netmask'] = self.netsettings[newsettings
                   ['ADMIN_NETWORK']['interface']]["netmask"]
        newsettings['ADMIN_NETWORK']['cidr'] = network.getCidr(
            self.netsettings[newsettings['ADMIN_NETWORK']['interface']][
                "addr"], newsettings['ADMIN_NETWORK']['netmask'])
        newsettings['ADMIN_NETWORK']['size'] = network.getCidrSize(
            newsettings['ADMIN_NETWORK']['cidr'])

        log.debug(str(newsettings))
        Settings().write(newsettings,
                         defaultsfile=self.parent.defaultsettingsfile,
                         outfn=self.parent.settingsfile)
        #Write naily.facts
        factsettings = dict()
        #for key in newsettings.keys():
        log.debug(str(facter_translate))
        log.debug(str(newsettings))
        for key in facter_translate.keys():
            factsettings[facter_translate[key]] = responses[key]
        n = nailyfactersettings.NailyFacterSettings()
        log.debug("Facts to write: %s" % factsettings)
        n.write(factsettings)

        #Set oldsettings to reflect new settings
        self.oldsettings = newsettings
        #Update DEFAULTS
        for index, fieldname in enumerate(fields):
            if fieldname != "blank" and "label" not in fieldname:
                DEFAULTS[fieldname]['value'] = responses[fieldname]

        self.parent.footer.set_text("Changes saved successfully.")

    def getNetwork(self):
        """Returns addr, broadcast, netmask for each network interface."""
        for iface in netifaces.interfaces():
            if 'lo' in iface or 'vir' in iface:
            #if 'lo' in iface or 'vir' in iface or 'vbox' in iface:
                if iface != "virbr2-nic":
                    continue
            try:
                self.netsettings.update({iface: netifaces.ifaddresses(iface)[
                    netifaces.AF_INET][0]})
                self.netsettings[iface]["onboot"] = "Yes"
            except Exception:
                self.netsettings.update({iface: {"addr": "", "netmask": "",
                                        "onboot": "no"}})
            self.netsettings[iface]['mac'] = netifaces.ifaddresses(iface)[
                netifaces.AF_LINK][0]['addr']

            #Set link state
            try:
                with open("/sys/class/net/%s/operstate" % iface) as f:
                    content = f.readlines()
                    self.netsettings[iface]["link"] = content[0].strip()
            except Exception:
                self.netsettings[iface]["link"] = "unknown"
            #Change unknown link state to up if interface has an IP
            if self.netsettings[iface]["link"] == "unknown":
                if self.netsettings[iface]["addr"] != "":
                    self.netsettings[iface]["link"] = "up"

            #Read bootproto from /etc/sysconfig/network-scripts/ifcfg-DEV
            self.netsettings[iface]['bootproto'] = "none"
            try:
                with open("/etc/sysconfig/network-scripts/ifcfg-%s" % iface)\
                        as fh:
                    for line in fh:
                        if re.match("^BOOTPROTO=", line):
                            self.netsettings[iface]['bootproto'] = \
                                line.split('=').strip()
                            break
            except Exception:
                #Check for dhclient process running for this interface
                if self.getDHCP(iface):
                    self.netsettings[iface]['bootproto'] = "dhcp"
                else:
                    self.netsettings[iface]['bootproto'] = "none"
        self.gateway = self.get_default_gateway_linux()

    def getDHCP(self, iface):
        """Returns True if the interface has a dhclient process running."""
        noout = open('/dev/null', 'w')
        dhclient_running = subprocess.call(["pgrep", "-f", "dhclient.*%s" %
                                           (iface)], stdout=noout,
                                           stderr=noout)
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
        """Update network details and display information."""
        ### Urwid returns the previously selected radio button.
        ### The previous object has True state, which is wrong.
        ### Somewhere in rb group a RadioButton is set to True.
        for rb in current.group:
            if rb.get_label() == current.get_label():
                continue
            if rb.base_widget.state is True:
                self.activeiface = rb.base_widget.get_label()
                self.parent.managediface = self.activeiface
                break
        self.gateway = self.get_default_gateway_linux()
        self.getNetwork()
        self.setNetworkDetails()
        return

    def setNetworkDetails(self):
        self.net_text1.set_text("Interface: %-13s  Link: %s" % (
            self.activeiface, self.netsettings[self.activeiface]['link'].
            upper()))
        self.net_text2.set_text("IP:      %-15s  MAC: %s" % (self.netsettings[
            self.activeiface]['addr'],
            self.netsettings[self.activeiface]['mac']))
        self.net_text3.set_text("Netmask: %-15s  Gateway: %s" % (
            self.netsettings[self.activeiface]['netmask'],
            self.gateway))
        log.debug("bootproto for %s: %s" % (self.netsettings[self.activeiface],
                  self.netsettings[self.activeiface]['bootproto']))
        if self.netsettings[self.activeiface]['link'].upper() == "UP":
            if self.netsettings[self.activeiface]['bootproto'] == "dhcp":
                self.net_text4.set_text("WARNING: Cannot use interface running"
                                        " DHCP.\nReconfigure as static in "
                                        "Network Setup screen.")
            else:
                self.net_text4.set_text("")
        else:
            self.net_text4.set_text("WARNING: This interface is DOWN. "
                                    "Configure it first.")

        #If DHCP pool start and matches activeiface network, don't update
        #This means if you change your pool values, go to another page, then
        #go back, it will not reset your changes. But what is more likely is
        #you will change the network settings for interface eth0 and then come
        #back to this page to update your DHCP settings. If the inSameSubnet
        #test fails, just recalculate and set new values.
        for index, key in enumerate(fields):
            if key == "ADMIN_NETWORK/dhcp_pool_start":
                dhcp_start = self.edits[index].get_edit_text()
                break
        if network.inSameSubnet(dhcp_start,
                                self.netsettings[self.activeiface]['addr'],
                                self.netsettings[self.activeiface]['netmask']):
            log.debug("Existing network settings exist. Not changing.")
            return
        else:
            log.debug("Existing network settings missing or invalid. "
                      "Updating...")

        #Calculate and set Static/DHCP pool fields
        #Max IPs = net size - 2 (master node + bcast)
        #Add gateway so we exclude it
        net_ip_list = network.getNetwork(
            self.netsettings[self.activeiface]['addr'],
            self.netsettings[self.activeiface]['netmask'],
            self.gateway)
        try:
            half = int(len(net_ip_list) / 2)
            static_pool = list(net_ip_list[1:half])
            dhcp_pool = list(net_ip_list[half:])
            static_start = str(static_pool[0])
            static_end = str(static_pool[-1])
            dynamic_start = str(dhcp_pool[0])
            dynamic_end = str(dhcp_pool[-1])
            if self.net_text4.get_text() == "":
                self.net_text4.set_text("This network configuration can "
                                        "support %s nodes." % len(dhcp_pool))
        except Exception:
            #We don't have valid values, so mark all fields empty
            static_start = ""
            static_end = ""
            dynamic_start = ""
            dynamic_end = ""
        for index, key in enumerate(fields):
            if key == "ADMIN_NETWORK/static_pool_start":
                self.edits[index].set_edit_text(static_start)
            elif key == "ADMIN_NETWORK/static_pool_end":
                self.edits[index].set_edit_text(static_end)
            elif key == "ADMIN_NETWORK/dhcp_pool_start":
                self.edits[index].set_edit_text(dynamic_start)
            elif key == "ADMIN_NETWORK/dhcp_pool_end":
                self.edits[index].set_edit_text(dynamic_end)

    def refresh(self):
        self.getNetwork()
        self.setNetworkDetails()

    def screenUI(self):
        #Define your text labels, text fields, and buttons first
        text1 = urwid.Text("Settings for PXE booting of slave nodes.")
        text2 = urwid.Text("Select the interface where PXE will run:")
        #Current network settings
        self.net_text1 = widget.TextLabel("")
        self.net_text2 = widget.TextLabel("")
        self.net_text3 = widget.TextLabel("")
        self.net_text4 = widget.TextLabel("")
        log.debug("Default iface %s" % self.activeiface)
        self.net_choices = widget.ChoicesGroup(self,
                                               sorted(self.netsettings.keys()),
                                               default_value=self.activeiface,
                                               fn=self.radioSelectIface)

        self.edits = []
        toolbar = self.parent.footer
        for key in fields:
            #Example: key = hostname, label = Hostname, value = fuel-pm
            if key == "blank":
                self.edits.append(blank)
            elif DEFAULTS[key]["value"] == "radio":
                label = widget.TextLabel(DEFAULTS[key]["label"])
                choices = widget.ChoicesGroup(self, ["Yes", "No"],
                                              default_value="Yes",
                                              fn=self.radioSelectIface)
                self.edits.append(widget.Columns([label, choices]))
            elif DEFAULTS[key]["value"] == "label":
                self.edits.append(widget.TextLabel(DEFAULTS[key]["label"]))
            else:
                caption = DEFAULTS[key]["label"]
                default = DEFAULTS[key]["value"]
                tooltip = DEFAULTS[key]["tooltip"]
                self.edits.append(widget.TextField(key, caption, 23, default,
                                  tooltip, toolbar))

        #Button to check
        button_check = widget.Button("Check", self.check)
        #Button to revert to previously saved settings
        button_cancel = widget.Button("Cancel", self.cancel)
        #Button to apply (and check again)
        button_apply = widget.Button("Apply", self.apply)

        #Wrap buttons into Columns so it doesn't expand and look ugly
        if self.parent.globalsave:
            check_col = widget.Columns([button_check])
        else:
            check_col = widget.Columns([button_check, button_cancel,
                                       button_apply, ('weight', 2, blank)])

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
        self.listwalker = urwid.SimpleListWalker(self.listbox_content)
        screen = urwid.ListBox(self.listwalker)
        return screen
