# -*- coding: utf-8 -*-
'''
@since: 27 Jan 2012
@author: oblivion
'''
import urwid
import logging
import window


class PopUpDialog(window.Window):
    '''
    General purpose pop up dialog.
    '''
    signals = ['close', 'set']

    def __init__(self, body=None):
        '''
        Constructor
        '''
        #log.logger.debug('Creating pop up dialog')
        if body == None:
            body = urwid.Filler(urwid.Text(''))
        #Buttons
        #Save
        save_button = urwid.Button('Set')
        self.save_button = urwid.AttrMap(save_button, 'body', 'focus')
        urwid.connect_signal(save_button, 'click',
                             lambda button: self._emit("set"))
        #Back
        back_button = urwid.Button('Cancel')
        self.back_button = urwid.AttrMap(back_button, 'body', 'focus')
        urwid.connect_signal(back_button, 'click',
                             lambda button: self._emit("close"))
        buttons = list()
        buttons.append(self.save_button)
        buttons.append(self.back_button)
        #Feed it to a GridFlow widget
        self.button_bar = urwid.GridFlow(buttons, 10, 3, 1, 'center')
        #Create a footer by piling the buttons with the divide
        widget = urwid.Pile([urwid.AttrMap(urwid.Divider(u'─', 1, 0),
                                                'frame'), self.button_bar])
        #Frame with buttons as footer.
        self.body = urwid.Frame(body, footer=widget, focus_part='body')
        widget = urwid.AttrWrap(self.body, 'body')

        #log.logger.debug('Pop up created')
        #Window
        window.Window.__init__(self, widget)

    def change_focus(self):
        '''
        Change the focus item in the dialog.
        '''
        #Focus on options
        if self.body.get_focus() == 'body':
            self.body.set_focus('footer')
            self.button_bar.set_focus(self.save_button)
            #log.logger.debug('Change focus: save')
        #Focus on buttons
        elif self.body.get_focus() == 'footer':
            if self.button_bar.get_focus() == self.save_button:
                self.button_bar.set_focus(self.back_button)
                #log.logger.debug('Change focus: back')
            else:
                self.body.set_focus('body')
                #log.logger.debug('Change focus: body')

    def keypress(self, size, key):
        '''Handle tab key to change focus.'''
        self._w.keypress(size, key)
        if key == 'tab':
            #log.logger.debug('Handle key: tab')
            self.change_focus()
            return(None)
        if key == 'esc':
            #close
            self._emit('close')
            return # eat keypress
        return(key)


