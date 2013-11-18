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


def TextField(keyword, label, width, default_value=None, tooltip=None,
              toolbar=None, disabled=False, ispassword=False):
    """Returns an Urwid Edit object."""
    if ispassword:
        mask = "*"
    else:
        mask = None
    if not tooltip:
        edit_obj = urwid.Edit(('important', label.ljust(width)), default_value,
                              mask=mask)
    else:
        edit_obj = TextWithTip(('important', label.ljust(width)),
                               default_value, tooltip, toolbar, mask=mask)
    wrapped_obj = urwid.AttrWrap(edit_obj, 'editbx', 'editfc')
    if disabled:
        wrapped_obj = urwid.WidgetDisable(urwid.AttrWrap(edit_obj,
                                          'important', 'editfc'))
        #Add get_edit_text and set_edit_text to wrapped_obj so we can use later
        wrapped_obj.set_edit_text = edit_obj.set_edit_text
        wrapped_obj.get_edit_text = edit_obj.get_edit_text
    return wrapped_obj


def ChoicesGroup(self, choices, default_value=None, fn=None):
    """Returns list of RadioButtons in a one-line GridFlow."""
    rb_group = []

    for txt in choices:
        is_default = True if txt == default_value else False
        urwid.AttrWrap(urwid.RadioButton(rb_group, txt,
                       is_default, on_state_change=fn,
                       user_data=txt),
                       'buttn', 'buttnf')
    wrapped_choices = urwid.GridFlow(rb_group, 13, 3, 0, 'left')
    #Bundle rb_group so we can use it later easily
    wrapped_choices.rb_group = rb_group
    return wrapped_choices


def TextLabel(text):
    """Returns an Urwid text object."""
    return urwid.Text(text)


def HorizontalGroup(objects, cell_width, align="left"):
    """Returns a padded Urwid GridFlow object that is left aligned."""
    return urwid.Padding(urwid.GridFlow(objects, cell_width, 1, 0, align),
                         left=0, right=0, min_width=61)


def Columns(objects):
    """Returns a padded Urwid Columns object that is left aligned."""
    #   Objects is a list of widgets. Widgets may be optionally specified
    #   as a tuple with ('weight', weight, widget) or (width, widget).
    #   Tuples without a widget have a weight of 1."""
    return urwid.Padding(urwid.Columns(objects, 1),
                         left=0, right=0, min_width=61)


def Button(text, fn):
    """Returns a wrapped Button with reverse focus attribute."""
    button = urwid.Button(text, fn)
    return urwid.AttrMap(button, None, focus_map='reversed')


class TextWithTip(urwid.Edit):
    def __init__(self, label, default_value=None, tooltip=None, toolbar=None,
                 mask=None):
        urwid.Edit.__init__(self, caption=label, edit_text=default_value,
                            mask=mask)
        self.tip = tooltip
        self.toolbar = toolbar

    def render(self, size, focus=False):
        if focus:
            self.toolbar.set_text(self.tip)
        canv = super(TextWithTip, self).render(size, focus)
        return canv
