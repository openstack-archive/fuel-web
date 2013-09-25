#!/usr/bin/env python

import urwid
import urwid.raw_display
import urwid.web_display
import logging
import sys
import copy
<<<<<<< HEAD
import socket
import struct
=======
import socket, struct
>>>>>>> 265265e6e18510422b50eba78bac1483d41e5052
import re
import netaddr
sys.path.append("/home/mmosesohn/git/fuel/iso/fuelmenu")
from fuelmenu.settings import *
from fuelmenu.common.urwidwrapper import *
blank = urwid.Divider()


class ModalDialog(urwid.WidgetWrap):
    signals = ['close']

    title = None

<<<<<<< HEAD
    def __init__(self, title, body, escape_key, previous_widget, loop=None):
        self.escape_key = escape_key
        self.previous_widget = previous_widget
        self.keep_open = True
        self.loop = loop
=======
    def __init__(self, title, body, escape_key, previous_widget,loop=None):
        self.escape_key = escape_key
        self.previous_widget = previous_widget
        self.keep_open=True
        self.loop=loop
>>>>>>> 265265e6e18510422b50eba78bac1483d41e5052
        logging.debug("start modal")
        logging.debug(type(body))

        if type(body) in [str, unicode]:
            body = urwid.Text(body)
            logging.debug("Set text widget")
        self.title = title
<<<<<<< HEAD
        bodybox = urwid.LineBox(urwid.Pile([body, blank,
                                Button("Close", self.close)]), title)
        overlay = urwid.Overlay(urwid.Filler(bodybox), previous_widget,
                                'center', ('relative', 80), 'middle',
                                ('relative', 80))
        overlay_attrmap = urwid.AttrMap(overlay, "body")
        super(ModalDialog, self).__init__(overlay_attrmap)
        logging.debug(overlay.contents[0])

    def close(self, arg):
        urwid.emit_signal(self, "close")
        self.keep_open = False
        self.loop.widget = self.previous_widget
=======
        bodybox = urwid.LineBox(urwid.Pile([body,blank,Button("Close", self.close)]), title)
        #overlay = urwid.Overlay(urwid.Pile([bodybox]), previous_widget, 'center',
        overlay = urwid.Overlay(urwid.Filler(bodybox), previous_widget, 'center',
('relative', 80), 'middle', ('relative', 80))
        #overlay = urwid.Overlay(body, previous_widget, 'center',
                                #80, "top", 24, 80, 24,
                                #0,0,0,0)
                                #100, 'bottom',
                                #100)
                                #('relative', 100), 'bottom',
                                #('relative', 100))
        overlay_attrmap = urwid.AttrMap(overlay, "body")
        #overlay_attrmap = urwid.AttrMap(overlay, "plugin.widget.dialog")
        super(ModalDialog, self).__init__(overlay_attrmap)
        logging.debug(overlay.contents[0])

    def close(self,arg):
        urwid.emit_signal(self, "close")
        self.keep_open=False
        self.loop.widget=self.previous_widget
>>>>>>> 265265e6e18510422b50eba78bac1483d41e5052

    def __repr__(self):
        return "<%s title='%s' at %s>" % (self.__class__.__name__, self.title,
                                          hex(id(self)))

<<<<<<< HEAD

def display_dialog(self, body, title, escape_key="esc"):
        filler = urwid.Pile([body])
        dialog = ModalDialog(title, filler, escape_key,
                             self.parent.mainloop.widget,
                             loop=self.parent.mainloop)
        self.parent.mainloop.widget = dialog
        return dialog
=======
def display_dialog(self, body, title, escape_key="esc"):
        filler = urwid.Pile([body])
        #dialog = urwid.Padding(ModalDialog(title, filler, escape_key,
        #                        self.parent.mainloop.widget))
        dialog = ModalDialog(title, filler, escape_key,
                                self.parent.mainloop.widget,
                                loop=self.parent.mainloop)
        #self.parent.frame.set_body(dialog)
        self.parent.mainloop.widget = dialog
        #self.parent.mainloop.widget = urwid.Padding(dialog,width=80)
        #self.__widget_stack.append(dialog)
        #self.force_redraw()
        #self.logger.debug("New Stack: %s" % self.__widget_stack)
        return dialog

>>>>>>> 265265e6e18510422b50eba78bac1483d41e5052
