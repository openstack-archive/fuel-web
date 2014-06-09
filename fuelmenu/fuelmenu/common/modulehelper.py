# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import fuelmenu.common.urwidwrapper as widget
from fuelmenu.settings import Settings
import logging
import netifaces
import re
import socket
import struct
import subprocess
import urwid
import urwid.raw_display
import urwid.web_display
log = logging.getLogger('fuelmenu.modulehelper')
blank = urwid.Divider()


class ModuleHelper(object):

    @classmethod
    def load(cls, modobj):
        #Read in yaml
        defaultsettings = Settings().read(modobj.parent.defaultsettingsfile)
        oldsettings = defaultsettings.copy()
        oldsettings.update(Settings().read(modobj.parent.settingsfile))
        for setting in modobj.defaults.keys():
            if "label" in setting:
                continue
            elif "/" in setting:
                part1, part2 = setting.split("/")
                modobj.defaults[setting]["value"] = oldsettings[part1][part2]
            else:
                modobj.defaults[setting]["value"] = oldsettings[setting]
        if modobj.netsettings and oldsettings["ADMIN_NETWORK"]["interface"] \
                in modobj.netsettings.keys():
            modobj.activeiface = oldsettings["ADMIN_NETWORK"]["interface"]
        return oldsettings

    @classmethod
    def save(cls, modobj, responses):
        newsettings = dict()
        for setting in responses.keys():
            if "/" in setting:
                part1, part2 = setting.split("/")
                if part1 not in newsettings:
                    #We may not touch all settings, so copy oldsettings first
                    newsettings[part1] = modobj.oldsettings[part1]
                newsettings[part1][part2] = responses[setting]
            else:
                newsettings[setting] = responses[setting]
        return newsettings

    @classmethod
    def cancel(self, cls, button=None):
        for index, fieldname in enumerate(cls.fields):
            if fieldname != "blank" and "label" not in fieldname:
                try:
                    cls.edits[index].set_edit_text(cls.defaults[fieldname][
                        'value'])
                except AttributeError:
                    log.warning("Field %s unable to reset text" % fieldname)

    @classmethod
    def screenUI(cls, modobj, headertext, fields, defaults,
                 showallbuttons=False, buttons_visible=True):

        log.debug("Preparing screen UI for %s" % modobj.name)
        #Define text labels, text fields, and buttons first
        header_content = []
        for text in headertext:
            if isinstance(text, str):
                header_content.append(urwid.Text(text))
            else:
                header_content.append(text)

        edits = []
        toolbar = modobj.parent.footer
        for key in fields:
            #Example: key = hostname, label = Hostname, value = fuel-pm
            if key == "blank":
                edits.append(blank)
            elif defaults[key]["value"] == "radio":
                label = widget.TextLabel(defaults[key]["label"])
                if "choices" in defaults[key]:
                    choices_list = defaults[key]["choices"]
                else:
                    choices_list = ["Yes", "No"]
                choices = widget.ChoicesGroup(choices_list,
                                              default_value="Yes",
                                              fn=modobj.radioSelect)
                columns = widget.Columns([('weight', 2, label),
                                         ('weight', 3, choices)])
                #Attach choices rb_group so we can use it later
                columns.rb_group = choices.rb_group
                edits.append(columns)
            elif defaults[key]["value"] == "label":
                edits.append(widget.TextLabel(defaults[key]["label"]))
            else:
                caption = defaults[key]["label"]
                default = defaults[key]["value"]
                tooltip = defaults[key]["tooltip"]
                edits.append(
                    widget.TextField(key, caption, 23, default, tooltip,
                                     toolbar))

        listbox_content = []
        listbox_content.extend(header_content)
        listbox_content.append(blank)
        listbox_content.extend(edits)
        listbox_content.append(blank)

        #Wrap buttons into Columns so it doesn't expand and look ugly
        if buttons_visible:
            #Button to check
            button_check = widget.Button("Check", modobj.check)
            #Button to revert to previously saved settings
            button_cancel = widget.Button("Cancel", modobj.cancel)
            #Button to apply (and check again)
            button_apply = widget.Button("Apply", modobj.apply)

            if modobj.parent.globalsave and showallbuttons is False:
                check_col = widget.Columns([button_check])
            else:
                check_col = widget.Columns([button_check, button_cancel,
                                           button_apply, ('weight', 2, blank)])
            listbox_content.append(check_col)

        #Add everything into a ListBox and return it
        listwalker = widget.TabbedListWalker(listbox_content)
        screen = urwid.ListBox(listwalker)
        modobj.edits = edits
        modobj.walker = listwalker
        modobj.listbox_content = listbox_content
        return screen

    @classmethod
    def getNetwork(cls, modobj):
        """Returns addr, broadcast, netmask for each network interface."""
        re_ifaces = re.compile(r"lo|vir|vbox|docker|veth")
        for iface in netifaces.interfaces():
            if re_ifaces.search(iface):
                    continue
            try:
                modobj.netsettings.update({iface: netifaces.ifaddresses(iface)[
                    netifaces.AF_INET][0]})
                modobj.netsettings[iface]["onboot"] = "Yes"
            except (TypeError, KeyError):
                modobj.netsettings.update({iface: {"addr": "", "netmask": "",
                                          "onboot": "no"}})
            modobj.netsettings[iface]['mac'] = netifaces.ifaddresses(iface)[
                netifaces.AF_LINK][0]['addr']

            #Set link state
            try:
                with open("/sys/class/net/%s/operstate" % iface) as f:
                    content = f.readlines()
                    modobj.netsettings[iface]["link"] = content[0].strip()
            except IOError:
                log.warning("Unable to read operstate file for %s" % iface)
                modobj.netsettings[iface]["link"] = "unknown"
            #Change unknown link state to up if interface has an IP
            if modobj.netsettings[iface]["link"] == "unknown":
                if modobj.netsettings[iface]["addr"] != "":
                    modobj.netsettings[iface]["link"] = "up"

            #Read bootproto from /etc/sysconfig/network-scripts/ifcfg-DEV
            modobj.netsettings[iface]['bootproto'] = "none"
            try:
                with open("/etc/sysconfig/network-scripts/ifcfg-%s" % iface)\
                        as fh:
                    for line in fh:
                        if re.match("^BOOTPROTO=", line):
                            modobj.netsettings[iface]['bootproto'] = \
                                line.split('=').strip()
                            break
            except Exception:
                #Check for dhclient process running for this interface
                if modobj.getDHCP(iface):
                    modobj.netsettings[iface]['bootproto'] = "dhcp"
                else:
                    modobj.netsettings[iface]['bootproto'] = "none"
        modobj.gateway = modobj.get_default_gateway_linux()

    @classmethod
    def getDHCP(cls, iface):
        """Returns True if the interface has a dhclient process running."""
        noout = open('/dev/null', 'w')
        dhclient_running = subprocess.call(["pgrep", "-f", "dhclient.*%s" %
                                           (iface)], stdout=noout,
                                           stderr=noout)
        return (dhclient_running == 0)

    @classmethod
    def get_default_gateway_linux(cls):
        """Read the default gateway directly from /proc."""
        with open("/proc/net/route") as fh:
            for line in fh:
                fields = line.strip().split()
                if fields[1] != '00000000' or not int(fields[3], 16) & 2:
                    continue
                return socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
