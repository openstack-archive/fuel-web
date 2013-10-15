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

import urwid
import urwid.raw_display
import urwid.web_display
import logging
import sys
import copy
import socket
import struct
import re
import netaddr
sys.path.append("/home/mmosesohn/git/fuel/iso/fuelmenu")
from fuelmenu.settings import *
from fuelmenu.common.urwidwrapper import *
blank = urwid.Divider()


class ModalDialog(urwid.WidgetWrap):
    signals = ['close']

    title = None

    def __init__(self, title, body, escape_key, previous_widget, loop=None):
        self.escape_key = escape_key
        self.previous_widget = previous_widget
        self.keep_open = True
        self.loop = loop

        if type(body) in [str, unicode]:
            body = urwid.Text(body)
        self.title = title
        bodybox = urwid.LineBox(urwid.Pile([body, blank,
                                Button("Close", self.close)]), title)
        overlay = urwid.Overlay(urwid.Filler(bodybox), previous_widget,
                                'center', ('relative', 80), 'middle',
                                ('relative', 80))
        overlay_attrmap = urwid.AttrMap(overlay, "body")
        super(ModalDialog, self).__init__(overlay_attrmap)

    def close(self, arg):
        urwid.emit_signal(self, "close")
        self.keep_open = False
        self.loop.widget = self.previous_widget

    def __repr__(self):
        return "<%s title='%s' at %s>" % (self.__class__.__name__, self.title,
                                          hex(id(self)))


def display_dialog(self, body, title, escape_key="esc"):
        filler = urwid.Pile([body])
        dialog = ModalDialog(title, filler, escape_key,
                             self.parent.mainloop.widget,
                             loop=self.parent.mainloop)
        self.parent.mainloop.widget = dialog
        return dialog
