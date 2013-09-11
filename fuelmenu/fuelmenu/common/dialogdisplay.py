#!/usr/bin/python
# -*- coding: utf-8 -*-

import urwid

# Exceptions to handle DialogDisplay exit codes

class DialogExit(Exception):
    def __init__(self, exitcode = 0):
        self.exitcode = exitcode

class ChildDialogExit(DialogExit):
    pass

class MainDialogExit(DialogExit):
    pass

class OffsetOverlay(urwid.Overlay):
    def calculate_padding_filler(self, size, focus):
        l, r, t, b = self.__super.calculate_padding_filler(size, focus)
        return l+1, max(0, r-1), t+1, max(0, b-1)
# MyFrame makes urwid.Frame switch
# focus between body and footer
# when pressing 'tab'

class PopUpDialog(urwid.WidgetWrap):
    """A dialog that appears with nothing but a close button """
    signals = ['close']
    def __init__(self):
        close_button = urwid.Button("that's pretty cool")
        urwid.connect_signal(close_button, 'click',
            lambda button:self._emit("close"))
        pile = urwid.Pile([urwid.Text(
            "^^ I'm attached to the widget that opened me. "
            "Try resizing the window!\n"), close_button])
        fill = urwid.Filler(pile)
        self.__super.__init__(urwid.AttrWrap(fill, 'popbg'))

class PopUp(urwid.PopUpLauncher):
    def __init__(self, original_widget, text):
        #self.__super.__init__(urwid.Button("click-me"))
        #urwid.connect_signal(self.original_widget, 'click',
        #    lambda button: self.open_pop_up())
        pass
    def create_pop_up(self):
        pop_up = PopUpDialog()
        urwid.connect_signal(pop_up, 'close',
            lambda button: self.close_pop_up())
        return pop_up

    def get_pop_up_parameters(self):
        return {'left':0, 'top':1, 'overlay_width':32, 'overlay_height':7}


#class MyFrame(urwid.Frame):
#    def keypress(self, size, key):
#        if key == 'tab':
#            if self.focus_part == 'body':
#                self.set_focus('footer')
#                return None
#            elif self.focus_part == 'footer':
#                self.set_focus('body')
#                return None
#            else:
#                # do default action if
#                # focus_part is 'header'
#                self.__super.keypress(size, key)
#        return self.__super.keypress(size, key)
# 
#class DialogDisplay(urwid.WidgetWrap):
#    palette = [
#        ('body','black','white'),
#        ('border','black','white'),
#        ('shadow','white','black'),
#        ('selectable','black', 'dark cyan'),
#        ('focus','black','dark cyan','bold'),
#        ('focustext','light gray','dark blue'),
#        ('button normal','light gray', 'dark blue', 'standout'),
#        ('button select','white',      'dark green'),
#       ]
#    parent = None
#    def __init__(self, text, width, height, body=None, loop=None):
#        width = int(width)
#        if width <= 0:
#            width = ('relative', 80)
#        height = int(height)
#        if height <= 0:
#            height = ('relative', 80)
#    
#        if body is None:
#            # fill space with nothing
#            self.body = urwid.SolidFill(' ')
#            fp = 'footer'
#        else:
#            self.body = body
#            fp = 'body'
#        self.frame = MyFrame(self.body, focus_part = fp)
#        if text is not None:
#            self.frame.header = urwid.Pile( [urwid.Text(text),
#                urwid.Divider(u'\u2550')] )
#        w = self.frame
#        
#        # pad area around listbox
#        w = urwid.Padding(w, ('fixed left',2), ('fixed right',2))
#        w = urwid.Filler(w, ('fixed top',1), ('fixed bottom',1))
#        w = urwid.AttrWrap(w, 'body')
#        
#        w = urwid.LineBox(w)
#        
#        # "shadow" effect
#        w = urwid.Columns( [w,('fixed', 1, urwid.AttrWrap(
#            urwid.Filler(urwid.Text(('border',' ')), "top")
#            ,'shadow'))])
#        w = urwid.Frame( w, footer = 
#            urwid.AttrWrap(urwid.Text(('border',' ')),'shadow'))
#        if loop is None:
#            # this dialog is the main window
#            # create outermost border area
#            w = urwid.Padding(w, 'center', width )
#            w = urwid.Filler(w, 'middle', height )
#            w = urwid.AttrWrap( w, 'border' )
#        else:
#            # this dialog is a child window
#            # overlay it over the parent window
#            self.loop = loop
#            self.parent = self.loop.widget
#            w = urwid.Overlay(w, self.parent, 'center', width+2, 'middle', height+2)
#        self.view = w
#        
#        # Call WidgetWrap.__init__ to correctly initialize ourselves
#        urwid.WidgetWrap.__init__(self, self.view)
#
#
#    def add_buttons(self, buttons):
#        l = []
#        for name, exitcode in buttons:
#            b = urwid.Button( name, self.button_press )
#            b.exitcode = exitcode
#            b = urwid.AttrWrap( b, 'button normal','button select' )
#            l.append( b )
#        self.buttons = urwid.GridFlow(l, 10, 3, 1, 'center')
#        self.frame.footer = urwid.Pile( [ urwid.Divider(u'\u2500'),
#            self.buttons ], focus_item = 1)
#
#    def button_press(self, button):
#        if self.parent is None:
#            # We are the main window,
#            # so raise an exception to
#            # quit the main loop
#            raise MainDialogExit(button.exitcode)
#        else:
#            # We are a child window,
#            # so restore the parent widget
#            # then raise a ChildDialogExit exception
#            self.loop.widget=self.parent
#            raise ChildDialogExit(button.exitcode)
#
#    def show(self):
#        if self.loop is None:
#            self.loop = urwid.MainLoop(self.view, self.palette)
#            exited = False
#            while not exited:
#                try:
#                    self.loop.run()
#                except ChildDialogExit as e:
#                    # Determine which dialog has exited
#                    # and act accordingly
#                    pass
#                except MainDialogExit:
#                    exited = True
#        else:
#            self.loop.widget = self.view
#
