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

import logging
import operator
from optparse import OptionParser
import os
from settings import Settings
import subprocess
import sys
import urwid
import urwid.raw_display
import urwid.web_display

# set up logging
logging.basicConfig(filename='/var/log/fuelmenu.log',
                    format="%(asctime)s %(levelname)s %(message)s",
                    level=logging.DEBUG)
log = logging.getLogger('fuelmenu.loader')


class Loader(object):

    def __init__(self, parent):
        self.modlist = []
        self.choices = []
        self.child = None
        self.children = []
        self.childpage = None
        self.parent = parent

    def load_modules(self, module_dir):
        if module_dir not in sys.path:
            sys.path.append(module_dir)

        modules = [os.path.splitext(f)[0] for f in os.listdir(module_dir)
                   if f.endswith('.py')]

        for module in modules:
            log.info('loading module %s' % module)
            try:
                imported = __import__(module)
                pass
            except ImportError as e:
                log.error('module could not be imported: %s' % e)
                continue

            clsobj = getattr(imported, module, None)
            modobj = clsobj(self.parent)

            # add the module to the list
            self.modlist.append(modobj)
        # sort modules
        self.modlist.sort(key=operator.attrgetter('priority'))
        for module in self.modlist:
            self.choices.append(module.name)
        return (self.modlist, self.choices)


class FuelSetup(object):

    def __init__(self):
        self.footer = None
        self.frame = None
        self.screen = None
        self.defaultsettingsfile = "%s/settings.yaml" \
                                   % (os.path.dirname(__file__))
        self.settingsfile = "/etc/fuel/astute.yaml"
        self.managediface = "eth0"
        #Set to true to move all settings to end
        self.globalsave = True
        self.version = self.getVersion("/etc/fuel/version.yaml")
        self.main()
        self.choices = []

    def menu(self, title, choices):
        body = [urwid.Text(title), urwid.Divider()]
        for c in choices:
            button = urwid.Button(c)
            urwid.connect_signal(button, 'click', self.menu_chosen, c)
            body.append(urwid.AttrMap(button, None, focus_map='reversed'))
        return urwid.ListBox(urwid.SimpleListWalker(body))
        #return urwid.ListBox(urwid.SimpleFocusListWalker(body))

    def menu_chosen(self, button, choice):
        size = self.screen.get_cols_rows()
        self.screen.draw_screen(size, self.frame.render(size))
        for item in self.menuitems.body.contents:
            try:
                if item.original_widget and \
                        item.original_widget.get_label() == choice:
                    item.set_attr_map({None: 'header'})
                else:
                    item.set_attr_map({None: None})
            except Exception as e:
                log.info("%s" % item)
                log.error("%s" % e)
        self.setChildScreen(name=choice)

    def setChildScreen(self, name=None):
        if name is None:
            self.child = self.children[0]
        else:
            self.child = self.children[int(self.choices.index(name))]
        if not self.child.screen:
            self.child.screen = self.child.screenUI()
        self.childpage = self.child.screen
        self.childfill = urwid.Filler(self.childpage, 'top', 40)
        self.childbox = urwid.BoxAdapter(self.childfill, 40)
        self.cols = urwid.Columns(
            [
                ('fixed', 20, urwid.Pile([
                    urwid.AttrMap(self.menubox, 'bright'),
                    urwid.Divider(" ")])),
                ('weight', 3, urwid.Pile([
                    urwid.Divider(" "),
                    self.childbox,
                    urwid.Divider(" ")]))
            ], 1)
        self.child.refresh()
        self.listwalker[:] = [self.cols]

    def refreshScreen(self):
        size = self.screen.get_cols_rows()
        self.screen.draw_screen(size, self.frame.render(size))

    def refreshChildScreen(self, name):
        child = self.children[int(self.choices.index(name))]
        #Refresh child listwalker
        child.listwalker[:] = child.listbox_content

        #reassign childpage top level objects
        self.childpage = urwid.ListBox(child.listwalker)
        self.childfill = urwid.Filler(self.childpage, 'middle', 22)
        self.childbox = urwid.BoxAdapter(self.childfill, 22)
        self.cols = urwid.Columns(
            [
                ('fixed', 20, urwid.Pile([
                    urwid.AttrMap(self.menubox, 'bright'),
                    urwid.Divider(" ")])),
                ('weight', 3, urwid.Pile([
                    urwid.Divider(" "),
                    self.childbox,
                    urwid.Divider(" ")]))
            ], 1)
        #Refresh top level listwalker
        #self.listwalker[:] = [self.cols]

    def getVersion(self, versionfile):
        try:
            versiondata = Settings().read(versionfile)
            return versiondata['release']
        except (IOError, KeyError):
            log.error("Unable to set Fuel version from %s" % versionfile)
            return ""

    def main(self):
        #Disable kernel print messages. They make our UI ugly
        noout = open('/dev/null', 'w')
        subprocess.call(["sysctl", "-w", "kernel.printk=4 1 1 7"],
                        stdout=noout, stderr=noout)

        text_header = (u"Fuel %s setup "
                       u"Use Up/Down/Left/Right to navigate.  F8 exits."
                       % self.version)
        text_footer = (u"Status messages go here.")

        #Top and bottom lines of frame
        self.header = urwid.AttrWrap(urwid.Text(text_header), 'header')
        self.footer = urwid.AttrWrap(urwid.Text(text_footer), 'footer')

        #Prepare submodules
        loader = Loader(self)
        moduledir = "%s/modules" % (os.path.dirname(__file__))
        self.children, self.choices = loader.load_modules(module_dir=moduledir)

        if len(self.children) == 0:
            import sys
            sys.exit(1)
        #Build list of choices excluding visible
        self.visiblechoices = []
        for child, choice in zip(self.children, self.choices):
            if child.visible:
                self.visiblechoices.append(choice)

        self.menuitems = self.menu(u'Menu', self.visiblechoices)
        menufill = urwid.Filler(self.menuitems, 'top', 40)
        self.menubox = urwid.BoxAdapter(menufill, 40)

        self.child = self.children[0]
        self.childpage = self.child.screenUI()
        self.childfill = urwid.Filler(self.childpage, 'top', 22)
        self.childbox = urwid.BoxAdapter(self.childfill, 22)
        self.cols = urwid.Columns(
            [
                ('fixed', 20, urwid.Pile([
                    urwid.AttrMap(self.menubox, 'bright'),
                    urwid.Divider(" ")])),
                ('weight', 3, urwid.Pile([
                    urwid.Divider(" "),
                    self.childbox,
                    urwid.Divider(" ")]))
            ], 1)
        self.listwalker = urwid.SimpleListWalker([self.cols])
        #self.listwalker = urwid.TreeWalker([self.cols])
        self.listbox = urwid.ListBox(self.listwalker)
        #listbox = urwid.ListBox(urwid.SimpleListWalker(listbox_content))

        self.frame = urwid.Frame(urwid.AttrWrap(self.listbox, 'body'),
                                 header=self.header, footer=self.footer)

        palette = \
            [
                ('body', 'black', 'light gray', 'standout'),
                ('reverse', 'light gray', 'black'),
                ('header', 'white', 'dark red', 'bold'),
                ('important', 'dark blue', 'light gray',
                    ('standout', 'underline')),
                ('editfc', 'white', 'dark blue', 'bold'),
                ('editbx', 'light gray', 'dark blue'),
                ('editcp', 'black', 'light gray', 'standout'),
                ('bright', 'dark gray', 'light gray', ('bold', 'standout')),
                ('buttn', 'black', 'dark cyan'),
                ('buttnf', 'white', 'dark blue', 'bold'),
                ('light gray', 'white', 'light gray', 'bold'),
                ('red', 'dark red', 'light gray', 'bold'),
                ('black', 'black', 'black', 'bold'),
            ]

        # use appropriate Screen class
        if urwid.web_display.is_web_request():
            self.screen = urwid.web_display.Screen()
        else:
            self.screen = urwid.raw_display.Screen()

        def unhandled(key):
            if key == 'f8':
                raise urwid.ExitMainLoop()
            if key == 'shift tab':
                self.child.walker.tab_prev()
            if key == 'tab':
                self.child.walker.tab_next()

        self.mainloop = urwid.MainLoop(self.frame, palette, self.screen,
                                       unhandled_input=unhandled)
        #Initialize each module completely before any events are handled
        for child in reversed(self.children):
            self.setChildScreen(name=child.name)
        #Prepare DNS for resolution
        dnsobj = self.children[int(self.choices.index("DNS & Hostname"))]
        dnsobj.setEtcResolv()

        self.mainloop.run()

    def exit_program(self, button):
        #return kernel logging to normal
        noout = open('/dev/null', 'w')
        subprocess.call(["sysctl", "-w", "kernel.printk=7 4 1 7"],
                        stdout=noout, stderr=noout)
        #Fix /etc/hosts and /etc/resolv.conf before quitting
        dnsobj = self.children[int(self.choices.index("DNS & Hostname"))]
        dnsobj.fixEtcHosts()
        dnsobj.setEtcResolv('127.0.0.1')

        raise urwid.ExitMainLoop()

    def global_save(self):
        #Runs save function for every module
        for module, modulename in zip(self.children, self.choices):
            #Run invisible modules. They may not have screen methods
            if not module.visible:
                try:
                    module.apply(None)
                except Exception as e:
                    log.error("Unable to save module %s: %s" % (modulename, e))
                    continue
            else:
                try:
                    log.info("Checking and applying module: %s"
                             % modulename)
                    self.footer.set_text("Checking and applying module: %s"
                                         % modulename)
                    self.refreshScreen()
                    module.refresh()
                    if module.apply(None):
                        log.info("Saving module: %s" % modulename)
                    else:
                        return False, modulename
                except AttributeError as e:
                    log.debug("Module %s does not have save function: %s"
                              % (modulename, e))
        return True, None


def setup():
    urwid.web_display.set_preferences("Fuel Setup")
    # try to handle short web requests quickly
    if urwid.web_display.handle_short_request():
        return
    FuelSetup()


def save_only(iface):
    import common.network as network
    from common import pwgen
    import netifaces

    #Calculate and set Static/DHCP pool fields
    #Max IPs = net size - 2 (master node + bcast)
    try:
        ip = netifaces.ifaddresses(iface)[netifaces.AF_INET][0]['addr']
        netmask = netifaces.ifaddresses(iface)[netifaces.AF_INET][0]['netmask']
        mac = netifaces.ifaddresses(iface)[netifaces.AF_LINK][0]['addr']
    except Exception:
        print("Interface %s is missing either IP address or netmask"
              % (iface))
        sys.exit(1)
    net_ip_list = network.getNetwork(ip, netmask)
    try:
        half = int(len(net_ip_list) / 2)
        #In most cases, skip 10.XXX.0.1
        static_pool = list(net_ip_list[1:half])
        dhcp_pool = list(net_ip_list[half:])
        static_start = str(static_pool[0])
        static_end = str(static_pool[-1])
        dynamic_start = str(dhcp_pool[0])
        dynamic_end = str(dhcp_pool[-1])
    except Exception:
        print("Unable to define DHCP pools")
        sys.exit(1)
    try:
        hostname, sep, domain = os.uname()[1].partition('.')
    except Exception:
        print("Unable to calculate hostname and domain")
        sys.exit(1)
    settings = \
        {
            "ADMIN_NETWORK/interface": iface,
            "ADMIN_NETWORK/ipaddress": ip,
            "ADMIN_NETWORK/netmask": netmask,
            "ADMIN_NETWORK/mac": mac,
            "ADMIN_NETWORK/dhcp_pool_start": dynamic_start,
            "ADMIN_NETWORK/dhcp_pool_end": dynamic_end,
            "ADMIN_NETWORK/static_pool_start": static_start,
            "ADMIN_NETWORK/static_pool_end": static_end,
            "HOSTNAME": hostname,
            "DNS_DOMAIN": domain,
            "DNS_SEARCH": domain,
            "astute/user": "naily",
            "astute/password": pwgen.password(),
            "cobbler/user": "cobbler",
            "cobbler/password": pwgen.password(),
            "keystone/admin_token": pwgen.password(),
            "mcollective/user": "mcollective",
            "mcollective/password": pwgen.password(),
            "postgres/keystone_dbname": "keystone",
            "postgres/keystone_user": "keystone",
            "postgres/keystone_password": pwgen.password(),
            "postgres/nailgun_dbname": "nailgun",
            "postgres/nailgun_user": "nailgun",
            "postgres/nailgun_password": pwgen.password(),
            "postgres/ostf_dbname": "ostf",
            "postgres/ostf_user": "ostf",
            "postgres/ostf_password": pwgen.password(),
            "FUEL_ACCESS/user": "admin",
            "FUEL_ACCESS/password": "admin",
        }
    newsettings = dict()
    for setting in settings.keys():
        if "/" in setting:
            part1, part2 = setting.split("/")
            if part1 not in newsettings.keys():
                newsettings[part1] = {}
            newsettings[part1][part2] = settings[setting]
        else:
            newsettings[setting] = settings[setting]
    #Write astute.yaml
    Settings().write(newsettings, defaultsfile=None,
                     outfn="/etc/fuel/astute.yaml")


def main(*args, **kwargs):
    if urwid.VERSION < (1, 1, 0):
        print("This program requires urwid 1.1.0 or greater.")

    parser = OptionParser()
    parser.add_option("-s", "--save-only", dest="save_only",
                      action="store_true",
                      help="Save default values and exit.")

    parser.add_option("-i", "--iface", dest="iface", metavar="IFACE",
                      default="eth0", help="Set IFACE as primary.")

    options, args = parser.parse_args()

    if options.save_only:
        save_only(options.iface)
    else:
        setup()

if '__main__' == __name__ or urwid.web_display.is_web_request():
    setup()
