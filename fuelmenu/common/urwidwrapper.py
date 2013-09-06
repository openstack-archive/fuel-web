import urwid
import urwid.raw_display
import urwid.web_display

def TextField(keyword, label, width, default_value=None, tooltip=None, toolbar=None, disabled=False):
    """Returns an Urwid Edit object"""
    if not tooltip:
      edit_obj = urwid.Edit(('important', label.ljust(width)), default_value)
    else: 
      edit_obj = TextWithTip(('important', label.ljust(width)), default_value, tooltip, toolbar)
    wrapped_obj = urwid.AttrWrap(edit_obj, 'editbx', 'editfc')
    if disabled:
      wrapped_obj = urwid.WidgetDisable(urwid.AttrWrap(edit_obj, 'important', 'editfc'))
      #Add get_edit_text and set_edit_text to wrapped_obj so we can use later
      wrapped_obj.set_edit_text = edit_obj.set_edit_text
      wrapped_obj.get_edit_text = edit_obj.get_edit_text
    return wrapped_obj

def ChoicesGroup(self, choices, default_value=None, fn=None):
    """Returns list of RadioButtons and  a horizontal Urwid GridFlow with 
       radio choices on one line."""
    rb_group = []
    
    for txt in choices:
        #if default_value == None:
        #  is_default = "first True"
        #else:
        #   is_default = True if txt == default_value else False
        is_default = True if txt == default_value else False
        radio_button = urwid.AttrWrap(urwid.RadioButton(rb_group,
                txt, on_state_change=fn, user_data=txt), 'buttn','buttnf')
                #txt, is_default, on_state_change=self.radioSelect, user_data=txt), 'buttn','buttnf')
    wrapped_choices = urwid.GridFlow(rb_group, 13, 3, 0, 'left')
    #Bundle rb_group so we can use it later easily
    wrapped_choices.rb_group=rb_group
    #setattr(wrapped_choices.rb_group,
    #wrapped_choices = urwid.Padding(urwid.GridFlow(rb_group, 13, 3, 0, 
    #            'left'), left=4, right=3, min_width=13)
    return wrapped_choices
 
def TextLabel(text):
    """Returns an Urwid text object"""
    return urwid.Text(text)

def HorizontalGroup(objects, cell_width, align="left"):
    """Returns a padded Urwid GridFlow object that is left aligned"""
    return urwid.Padding(urwid.GridFlow(objects, cell_width, 1, 0, align), 
                 left=0,right=0,min_width=61)

def Columns(objects):
    """Returns a padded Urwid Columns object that is left aligned.
       Objects is a list of widgets. Widgets may be optionally specified
       as a tuple with ('weight', weight, widget) or (width, widget).
       Tuples without a widget have a weight of 1."""
    return urwid.Padding(urwid.Columns(objects, 1), 
                 left=0,right=0,min_width=61)

def Button(text, fn):
    """Returns a wrapped Button with reverse focus attribute"""
    button = urwid.Button(text, fn)
    return urwid.AttrMap(button, None, focus_map='reversed')

class TextWithTip(urwid.Edit):
    def __init__(self, label, default_value=None, tooltip=None, toolbar=None):
    #def __init__(self, keyword, label, width, default_value=None, tooltip=None, toolbar=None):
       #super(TextWithTip, self).__init__("")
       urwid.Edit.__init__(self, caption=label, edit_text=default_value)
       self.tip = tooltip
       self.toolbar = toolbar
    #def keypress(self, size, key):
    #   key = super(TextWithTip, self).keypress(size, key)
    #   self.toolbar.set_text(self.tip)
    #   return key
    def render(self, size, focus=False):
       if focus:
         self.toolbar.set_text(self.tip)
       canv = super(TextWithTip, self).render(size, focus)
       return canv
    #def mouse_event(self, size, event, button, x, y, focus):
    #   self.toolbar.set_text(self.tip)
    #   (maxcol,) = size
    #   if button==1:
    #       return self.move_cursor_to_coords( (maxcol,), x, y )


