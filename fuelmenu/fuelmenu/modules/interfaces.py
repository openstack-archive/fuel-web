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
from fuelmenu.common.modulehelper import ModuleHelper
from fuelmenu.common import network
from fuelmenu.common import puppet
from fuelmenu.common import replace
from fuelmenu.common import timeout
import fuelmenu.common.urwidwrapper as widget
import logging
import netaddr
import re
import socket
import traceback
import urwid
import urwid.raw_display
import urwid.web_display

blank = urwid.Divider()


#Need to define fields in order so it will render correctly


class interfaces(urwid.WidgetWrap):
    def __init__(self, parent):
        self.name = "Network Setup"
        self.priority = 5
        self.visible = True
        self.netsettings = dict()
        self.parent = parent
        self.screen = None
        self.log = logging
        self.log.basicConfig(filename='./fuelmenu.log', level=logging.DEBUG)
        self.log.info("init Interfaces")
        self.getNetwork()
        self.gateway = self.get_default_gateway_linux()
        self.activeiface = sorted(self.netsettings.keys())[0]
        self.extdhcp = True

        #UI text
        self.net_choices = widget.ChoicesGroup(sorted(self.netsettings.keys()),
                                               default_value=self.activeiface,
                                               fn=self.radioSelectIface)
        #Placeholders for network settings text
        self.net_text1 = widget.TextLabel("")
        self.net_text2 = widget.TextLabel("")
        self.net_text3 = widget.TextLabel("")
        self.header_content = [self.net_choices, self.net_text1,
                               self.net_text2, self.net_text3]
        self.fields = ["blank", "ifname", "onboot", "bootproto", "ipaddr",
                       "netmask", "gateway"]
        self.defaults = \
            {
                "ifname": {"label": "Interface name:",
                           "tooltip": "Interface system identifier",
                           "value": "locked"},
                "onboot": {"label": "Enable interface:",
                           "tooltip": "",
                           "value": "radio"},
                "bootproto": {"label": "Configuration via DHCP:",
                              "tooltip": "",
                              "value": "radio",
                              "choices": ["DHCP", "Static"]},
                "ipaddr": {"label": "IP address:",
                           "tooltip": "Manual IP address (example \
192.168.1.2)",
                           "value": ""},
                "netmask": {"label": "Netmask:",
                            "tooltip": "Manual netmask (example \
255.255.255.0)",
                            "value": "255.255.255.0"},
                "gateway": {"label": "Default Gateway:",
                            "tooltip": "Manual gateway to access Internet \
(example 192.168.1.1)",
                            "value": ""},
            }

    def fixDnsmasqUpstream(self):
        #check upstream dns server
        with open('/etc/dnsmasq.upstream', 'r') as f:
            dnslines = f.readlines()
        nameservers = dnslines[0].split(" ")[1:]
        #for nameserver in nameservers:
        #    if not self.checkDNS(nameserver):
        #        nameservers.remove(nameserver)
        if nameservers == []:
            #Write dnsmasq upstream server to default if it's not readable
            with open('/etc/dnsmasq.upstream', 'w') as f:
                nameservers = self.defaults['DNS_UPSTREAM']['value'].replace(
                    ',', ' ')
                f.write("nameserver %s\n" % nameservers)
                f.close()

    def fixEtcHosts(self):
        #replace ip for env variable HOSTNAME in /etc/hosts
        if self.netsettings[self.parent.managediface]["addr"] != "":
            managediface_ip = self.netsettings[self.parent.managediface][
                "addr"]
        else:
            managediface_ip = "127.0.0.1"
        found = False
        with open("/etc/hosts") as fh:
            for line in fh:
                if re.match("%s.*%s" % (managediface_ip, socket.gethostname()),
                            line):
                    found = True
                    break
        if not found:
            expr = ".*%s.*" % socket.gethostname()
            replace.replaceInFile("/etc/hosts", expr, "%s   %s %s" % (
                                  managediface_ip, socket.gethostname(),
                                  socket.gethostname().split(".")[0]))

    def check(self, args):
        """Validate that all fields have valid values and sanity checks."""
        #Get field information
        responses = dict()
        self.parent.footer.set_text("Checking data...")
        for index, fieldname in enumerate(self.fields):
            if fieldname == "blank" or fieldname == "ifname":
                pass
            elif fieldname == "bootproto":
                rb_group = self.edits[index].rb_group
                if rb_group[0].state:
                    responses["bootproto"] = "dhcp"
                else:
                    responses["bootproto"] = "none"
            elif fieldname == "onboot":
                rb_group = self.edits[index].rb_group
                if rb_group[0].state:
                    responses["onboot"] = "yes"
                else:
                    responses["onboot"] = "no"
            else:
                responses[fieldname] = self.edits[index].get_edit_text()

        ###Validate each field
        errors = []
        if responses["onboot"] == "no":
            numactiveifaces = 0
            for iface in self.netsettings:
                if self.netsettings[iface]['addr'] != "":
                    numactiveifaces += 1
            if numactiveifaces < 2 and \
                    self.netsettings[self.activeiface]['addr'] != "":
                #Block user because puppet l23network fails if all intefaces
                #are disabled.
                errors.append("Cannot disable all interfaces.")
        elif responses["bootproto"] == "dhcp":
            self.parent.footer.set_text("Scanning for DHCP servers. "
                                        "Please wait...")
            self.parent.refreshScreen()
            try:
                dhcptimeout = 5
                with timeout.run_with_timeout(dhcp_checker.utils.IfaceState,
                                              [self.activeiface],
                                              timeout=dhcptimeout) as iface:
                    dhcp_server_data = timeout.run_with_timeout(
                        dhcp_checker.api.check_dhcp_on_eth,
                        [iface, dhcptimeout], timeout=dhcptimeout)
            except (KeyboardInterrupt, timeout.TimeoutError):
                self.log.debug("DHCP scan timed out")
                self.log.warning(traceback.format_exc())
                dhcp_server_data = []
            except Exception:
                self.log.warning("dhcp_checker failed to check on %s"
                                 % self.activeiface)
                dhcp_server_data = []
                responses["dhcp_nowait"] = False

            if len(dhcp_server_data) < 1:
                self.log.debug("No DHCP servers found. Warning user about "
                               "dhcp_nowait.")
                #Build dialog elements
                dhcp_info = []
                dhcp_info.append(urwid.Padding(
                                 urwid.Text(("header", "!!! WARNING !!!")),
                                 "center"))
                dhcp_info.append(
                    widget.TextLabel(
                        "Unable to detect DHCP server" +
                        "on interface %s." % (self.activeiface) +
                        "\nDHCP will be set up in the background, " +
                        "but may not receive an IP address. You may " +
                        "want to check your DHCP connection manually " +
                        "using the Shell Login menu to the left."))
                dialog.display_dialog(self, urwid.Pile(dhcp_info),
                                      "DHCP Servers Found on %s"
                                      % self.activeiface)
                self.parent.refreshScreen()
                responses["dhcp_nowait"] = True
        #Check ipaddr, netmask, gateway only if static
        elif responses["bootproto"] == "none":
            try:
                if netaddr.valid_ipv4(responses["ipaddr"]):
                    if not netaddr.IPAddress(responses["ipaddr"]):
                        raise BadIPException("Not a valid IP address")
                else:
                    raise BadIPException("Not a valid IP address")
            except (BadIPException, Exception):
                errors.append("Not a valid IP address: %s" %
                              responses["ipaddr"])
            try:
                if netaddr.valid_ipv4(responses["netmask"]):
                    netmask = netaddr.IPAddress(responses["netmask"])
                    if netmask.is_netmask is False:
                        raise BadIPException("Not a valid IP address")
                else:
                    raise BadIPException("Not a valid IP address")
            except (BadIPException, Exception):
                errors.append("Not a valid netmask: %s" % responses["netmask"])
            try:
                if len(responses["gateway"]) > 0:
                    #Check if gateway is valid
                    if netaddr.valid_ipv4(responses["gateway"]) is False:
                        raise BadIPException("Gateway IP address is not valid")
                    #Check if gateway is in same subnet
                    if network.inSameSubnet(responses["ipaddr"],
                                            responses["gateway"],
                                            responses["netmask"]) is False:
                        raise BadIPException("Gateway IP is not in same "
                                             "subnet as IP address")
            except (BadIPException, Exception) as e:
                errors.append(e)
        if len(errors) > 0:
            self.parent.footer.set_text("Error: %s" % (errors[0]))
            self.log.error("Errors: %s %s" % (len(errors), errors))
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

        self.parent.footer.set_text("Applying changes... (May take up to 20s)")
        puppetclasses = []
        l3ifconfig = {'type': "resource",
                      'class': "l23network::l3::ifconfig",
                      'name': self.activeiface}
        if responses["onboot"].lower() == "no":
            params = {"ipaddr": "none"}
        elif responses["bootproto"] == "dhcp":
            if "dhcp_nowait" in responses.keys():
                params = {"ipaddr": "dhcp",
                          "dhcp_nowait": responses["dhcp_nowait"]}
            else:
                params = {"ipaddr": "dhcp"}
        else:
            params = {"ipaddr": responses["ipaddr"],
                      "netmask": responses["netmask"],
                      "check_by_ping": "none"}
        if len(responses["gateway"]) > 1:
            params["gateway"] = responses["gateway"]
            params["default_gateway"] = True
        elif network.inSameSubnet(self.get_default_gateway_linux(),
                                  responses["ipaddr"], responses["netmask"]):
            #If the current gateway is in the same subnet AND the user
            #sets the gateway to empty, unset gateway
            expr = '^GATEWAY=.*'
            replace.replaceInFile("/etc/sysconfig/network", expr,
                                  "GATEWAY=")
        l3ifconfig['params'] = params
        puppetclasses.append(l3ifconfig)
        self.log.info("Puppet data: %s" % (puppetclasses))
        try:
            #Gateway handling so DHCP will set gateway
            if responses["bootproto"] == "dhcp":
                expr = '^GATEWAY=.*'
                replace.replaceInFile("/etc/sysconfig/network", expr,
                                      "GATEWAY=")
            self.parent.refreshScreen()
            puppet.puppetApply(puppetclasses)
            ModuleHelper.getNetwork(self)
            expr = '^GATEWAY=.*'
            gateway = self.get_default_gateway_linux()
            if gateway is None:
                gateway = ""
            replace.replaceInFile("/etc/sysconfig/network", expr, "GATEWAY=%s"
                                  % gateway)
            self.fixEtcHosts()

        except Exception as e:
            self.log.error(e)
            self.parent.footer.set_text("Error applying changes. Check logs "
                                        "for details.")
            ModuleHelper.getNetwork(self)
            self.setNetworkDetails()
            return False
        self.parent.footer.set_text("Changes successfully applied.")
        ModuleHelper.getNetwork(self)
        self.setNetworkDetails()

        return True

    def getNetwork(self):
        ModuleHelper.getNetwork(self)

    def getDHCP(self, iface):
        return ModuleHelper.getDHCP(iface)

    def get_default_gateway_linux(self):
        return ModuleHelper.get_default_gateway_linux()

    def radioSelectIface(self, current, state, user_data=None):
        """Update network details and display information."""
        ### This makes no sense, but urwid returns the previous object.
        ### The previous object has True state, which is wrong.
        ### Somewhere in current.group a RadioButton is set to True.
        ### Our quest is to find it.
        for rb in current.group:
            if rb.get_label() == current.get_label():
                continue
            if rb.base_widget.state is True:
                self.activeiface = rb.base_widget.get_label()
                break
        ModuleHelper.getNetwork(self)
        self.setNetworkDetails()

    def radioSelect(self, current, state, user_data=None):
        """Update network details and display information."""
        ### This makes no sense, but urwid returns the previous object.
        ### The previous object has True state, which is wrong.
        ### Somewhere in current.group a RadioButton is set to True.
        ### Our quest is to find it.
        for rb in current.group:
            if rb.get_label() == current.get_label():
                continue
            if rb.base_widget.state is True:
                self.extdhcp = (rb.base_widget.get_label() == "Yes")
                break

    def setNetworkDetails(self):
        self.net_text1.set_text("Interface: %-13s  Link: %s" % (
            self.activeiface,
            self.netsettings[self.activeiface]['link'].upper()))

        self.net_text2.set_text("IP:      %-15s  MAC: %s" % (
            self.netsettings[self.activeiface]['addr'],
            self.netsettings[self.activeiface]['mac']))
        self.net_text3.set_text("Netmask: %-15s  Gateway: %s" % (
            self.netsettings[self.activeiface]['netmask'],
            self.gateway))
        #Set text fields to current netsettings
        for index, fieldname in enumerate(self.fields):
            if fieldname == "ifname":
                self.edits[index].base_widget.set_edit_text(self.activeiface)
            elif fieldname == "bootproto":
                rb_group = self.edits[index].rb_group
                for rb in rb_group:
                    if self.netsettings[self.activeiface]["bootproto"].lower()\
                            == "dhcp":
                        rb_group[0].set_state(True)
                        rb_group[1].set_state(False)
                    else:
                        rb_group[0].set_state(False)
                        rb_group[1].set_state(True)
            elif fieldname == "onboot":
                rb_group = self.edits[index].rb_group
                for rb in rb_group:
                    if self.netsettings[self.activeiface]["onboot"].lower()\
                            == "yes":
                        rb_group[0].set_state(True)
                        rb_group[1].set_state(False)
                else:
                    #onboot should only be no if the interface is also down
                    if self.netsettings[self.activeiface]['addr'] == "":
                        rb_group[0].set_state(False)
                        rb_group[1].set_state(True)
                    else:
                        rb_group[0].set_state(True)
                        rb_group[1].set_state(False)

            elif fieldname == "ipaddr":
                self.edits[index].set_edit_text(self.netsettings[
                    self.activeiface]['addr'])
            elif fieldname == "netmask":
                self.edits[index].set_edit_text(self.netsettings[
                    self.activeiface]['netmask'])
            elif fieldname == "gateway":
                #Gateway is for this iface only if gateway is matches subnet
                if network.inSameSubnet(
                        self.netsettings[self.activeiface]['addr'],
                        self.gateway,
                        self.netsettings[self.activeiface]['netmask']):
                    self.edits[index].set_edit_text(self.gateway)
                else:
                    self.edits[index].set_edit_text("")

    def refresh(self):
        ModuleHelper.getNetwork(self)
        self.setNetworkDetails()

    def cancel(self, button):
        ModuleHelper.cancel(self, button)
        self.setNetworkDetails()

    def screenUI(self):
        return ModuleHelper.screenUI(self, self.header_content, self.fields,
                                     self.defaults, showallbuttons=True)
