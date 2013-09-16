'''
@since: 8 Feb 2012
@author: oblivion
'''
import urwid
#import log


class Window(urwid.WidgetWrap):
    '''
    A window with a line as frame.
    '''
    def __init__(self, w):
        '''
        Create the window.

        @param w: The widget to display inside the window.
        @type w: urwid.Widget
        '''
        #log.logger.debug("Creating Window instance")

        #Put a line around it
        widget = urwid.AttrMap(urwid.LineBox(w), 'frame')

        #shadow
        widget = urwid.Columns([widget, ('fixed', 2,
                                         urwid.Filler(urwid.Text(('bg', '  ')
                                                                   ), 'top'))])
        widget = urwid.Frame(widget, footer=urwid.Text(('bg', '  ')))
        widget = urwid.AttrMap(widget, 'shadow')

        urwid.WidgetWrap.__init__(self, widget)


