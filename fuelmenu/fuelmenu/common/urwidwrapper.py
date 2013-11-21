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
import urwid
import urwid.raw_display
import urwid.web_display
log = logging.getLogger('fuelmenu.urwidwrapper')


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


def ChoicesGroup(choices, default_value=None, fn=None):
    """Returns list of RadioButtons in a one-line GridFlow."""
    rb_group = []

    for txt in choices:
        is_default = True if txt == default_value else False
        urwid.AttrWrap(urwid.RadioButton(rb_group, txt,
                       is_default, on_state_change=fn,
                       user_data=txt),
                       'buttn', 'buttnf')
    wrapped_choices = TabbedGridFlow(rb_group, 13, 3, 0, 'left')
    #Bundle rb_group so it can be used later easily
    wrapped_choices.rb_group = rb_group
    return wrapped_choices


def TextLabel(text):
    """Returns an Urwid text object."""
    return urwid.Text(text)


def Columns(objects):
    """Returns a padded Urwid Columns object that is left aligned."""
    #   Objects is a list of widgets. Widgets may be optionally specified
    #   as a tuple with ('weight', weight, widget) or (width, widget).
    #   Tuples without a widget have a weight of 1."""
    return urwid.Padding(TabbedColumns(objects, 1),
                         left=0, right=0, min_width=61)


def Button(text, fn):
    """Returns a wrapped Button with reverse focus attribute."""
    button = urwid.Button(text, fn)
    return urwid.AttrMap(button, None, focus_map='reversed')


class TabbedGridFlow(urwid.GridFlow):

    def __init__(self, cells, cell_width, h_sep, v_sep, align):
        urwid.GridFlow.__init__(self, cells=cells, cell_width=cell_width,
                                h_sep=h_sep, v_sep=v_sep, align=align)

    def keypress(self, size, key):
        if key == 'tab' and self.focus_position < (len(self.contents) - 1)\
                and self.contents[self.focus_position + 1][0].selectable():
            self.tab_next(self.focus_position)
        elif key == 'shift tab' and self.focus_position > 0 \
                and self.contents[self.focus_position - 1][0].selectable():
            self.tab_prev(self.focus_position)
        else:
            return self.__super.keypress(size, key)

    def tab_next(self, pos):
        self.set_focus(pos + 1)
        maxlen = (len(self.contents) - 1)
        while pos < maxlen:
            if self.contents[pos][0].selectable():
                return
            else:
                pos += 1

        if pos >= maxlen:
            pos = 0
        self.set_focus(pos)

    def tab_prev(self, pos):
        self.set_focus(pos - 1)
        while pos > 0:
            if self.contents[pos][0].selectable():
                return
            else:
                pos -= 1
        if pos == 0:
            pos = (len(self.contents) - 1)

        self.set_focus(pos)

    def first_selectable(self):
        '''returns index of first selectable widget in contents.'''
        for pos, item in enumerate(self.contents):
            if item[0].selectable():
                return pos
        return (len(self.contents) - 1)


class TabbedColumns(urwid.Columns):

    def __init__(self, widget_list, dividechars=0, focus_column=None,
                 min_width=1, box_columns=None):
        urwid.Columns.__init__(self, widget_list,
                               dividechars=dividechars,
                               focus_column=focus_column,
                               min_width=min_width,
                               box_columns=box_columns)

    def keypress(self, size, key):
        if key == 'tab' and self.focus_position < (len(self.contents) - 1)\
                and self.widget_list[self.focus_position + 1].selectable():
            self.tab_next(self.focus_position)
        elif key == 'shift tab' and self.focus_position > 0 \
                and self.widget_list[self.focus_position - 1].selectable():
            self.tab_prev(self.focus_position)
        else:
            return self.__super.keypress(size, key)

    def tab_next(self, pos):
        self.set_focus(pos + 1)
        maxlen = (len(self.contents) - 1)
        while pos < maxlen:
            if self.widget_list[pos].selectable():
                return
            else:
                pos += 1

        if pos >= maxlen:
            pos = 0
        self.set_focus(pos)

    def tab_prev(self, pos):
        self.set_focus(pos - 1)
        while pos > 0:
            if self.widget_list[pos].selectable():
                return
            else:
                pos -= 1
        if pos == 0:
            pos = (len(self.widget_list) - 1)

        self.set_focus(pos)

    def first_selectable(self):
        '''returns index of first selectable widget in widget_list.'''
        for pos, item in enumerate(self.widget_list):
            if item.selectable():
                return pos
        return (len(self.widget_list) - 1)


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


class TabbedListWalker(urwid.ListWalker):
    def __init__(self, lst):
        self.lst = lst
        self.focus = 0

    def _modified(self):
        return urwid.ListWalker._modified(self)

    def tab_next(self):
        item, pos = self.get_next(self.focus)
        while pos is not None:
            if item.selectable():
                break
            else:
                item, pos = self.get_next(pos)
        if pos is None:
            pos = 0
        self.focus = pos
        self._modified()
        try:
            #Reset focus to first selectable widget in item
            if hasattr(item, 'original_widget'):
                item.original_widget.set_focus(
                    item.original_widget.first_selectable())
            else:
                item.set_focus(item.first_selectable())
        except Exception:
            #Ignore failure. Case only applies to TabbedColumns and
            #TabbedGridFlow. Other items should fail silently.
            pass

    def tab_prev(self):
        item, pos = self.get_prev(self.focus)
        while pos is not None:
            if item.selectable():
                break
            else:
                item, pos = self.get_prev(pos)

        if pos is None:
            pos = (len(self.lst) - 1)

        self.focus = pos
        self._modified()
        try:
            if hasattr(item, 'original_widget'):
                item.original_widget.set_focus(
                    len(item.original_widget.contents) - 1)
            else:
                item.set_focus(len(item.contents) - 1)
        except Exception:
            #Ignore failure. Case only applies to TabbedColumns and
            #TabbedGridFlow. Other items should fail silently.
            pass

    def get_focus(self):
        if self.lst:
            return self.lst[self.focus], self.focus
        else:
            return None, None

    def set_focus(self, focus):
        self.focus = focus

    def get_next(self, pos):
        if (pos + 1) >= len(self.lst):
            return None, None
        return self.lst[pos + 1], pos + 1

    def get_prev(self, pos):
        if (pos - 1) < 0:
            return None, None
        return self.lst[pos - 1], pos - 1
