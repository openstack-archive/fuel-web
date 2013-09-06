import urwid
import urwid.raw_display
import urwid.web_display
import sys
import operator
import os
import sys

# set up logging
import logging
logging.basicConfig(filename='./fuelmenu.log')
#logging.basicConfig(filename='./fuelmenu.log',level=logging.DEBUG)
log = logging.getLogger('fuelmenu.loader')

class Loader:

    def __init__(self, parent):
        self.modlist = []
        self.choices = []
        self.child = None
        self.children = []
        self.childpage = None
        self.parent = parent

    def load_modules(self, module_dir):
        if not module_dir in sys.path:
            sys.path.append(module_dir)

        modules = [os.path.splitext(f)[0] for f in os.listdir(module_dir)
                   if f.endswith('.py')]
        
        for module in modules:
            log.info('loading module %s', module)
            try:
                imported = __import__(module)
                pass
                #imported = process(module)
            except ImportError as e:
                log.error('module could not be imported: %s', e)
                continue

            clsobj = getattr(imported, module, None)
            modobj = clsobj(self.parent)

            # add the module to the list
            self.modlist.append(modobj)
        # sort modules
        self.modlist.sort(key=operator.attrgetter('priority'))
        for module in self.modlist:
            self.choices.append(module.name)
        return (self.modlist,self.choices)


version="3.2"
#choices= u"Status,Networking,OpenStack Setup,Terminal,Save & Quit".split(',')
class FuelSetup():

    def __init__(self):
        self.footer = None
        self.frame = None
        self.screen = None
        self.settingsfile = "settings.yaml"
        self.main()
        self.choices = []

    def menu(self, title, choices):
        body = [urwid.Text(title), urwid.Divider()]
        for c in choices:
            button = urwid.Button(c)
            urwid.connect_signal(button, 'click', self.menu_chosen, c)
            body.append(urwid.AttrMap(button, None, focus_map='reversed'))
        return urwid.ListBox(urwid.SimpleFocusListWalker(body))
    
    def menu_chosen(self, button, choice):
        size = self.screen.get_cols_rows()
        self.screen.draw_screen(size, self.frame.render(size))

        self.footer.set_text([u'You chose ', choice, u''])
        #self.child = self.children[self.choices.index(choice)]
        #self.childpage = self.child.screenUI()
        self.setChildScreen(name=choice)
        response = urwid.Text([u'You chose ', choice, u'\n'])
        done = urwid.Button(u'Ok')
        urwid.connect_signal(done, 'click', self.exit_program)
        self.frame.original_widget = urwid.Filler(urwid.Pile([response,
            urwid.AttrMap(done, None, focus_map='reversed')]))
    

    def setChildScreen(self, name=None):
        if name is None:
            child = self.children[0]
        else:
            log.info(name, self.choices.index(name))
            child = self.children[int(self.choices.index(name))]
        self.childpage = child.screenUI()
        self.childfill = urwid.Filler(self.childpage, 'top', 40)
        self.childbox = urwid.BoxAdapter(self.childfill, 40)
        self.cols = urwid.Columns([
                ('fixed', 20, urwid.Pile([
                    urwid.AttrMap(self.menubox, 'bright'),
                    urwid.Divider(" ")])),
                ('weight', 3, urwid.Pile([
                    urwid.Divider(" "),
                    self.childbox,
                    urwid.Divider(" ")]))
                ], 3)
        self.listwalker[:] = [self.cols]

    def refreshScreen(self):
        size = self.screen.get_cols_rows()
        self.screen.draw_screen(size, self.frame.render(size))

    def refreshChildScreen(self, name):
        child = self.children[int(self.choices.index(name))]
        #Refresh child listwalker
        child.listwalker[:]=child.listbox_content
        
        #reassign childpage top level objects
        self.childpage = urwid.ListBox(child.listwalker)
        self.childfill = urwid.Filler(self.childpage, 'middle', 22)
        self.childbox = urwid.BoxAdapter(self.childfill, 22)
        self.cols = urwid.Columns([
                ('fixed', 20, urwid.Pile([
                    urwid.AttrMap(self.menubox, 'bright'),
                    urwid.Divider(" ")])),
                ('weight', 3, urwid.Pile([
                    urwid.Divider(" "),
                    self.childbox,
                    urwid.Divider(" ")]))
                ], 3)
        #Refresh top level listwalker
        #self.listwalker[:] = [self.cols]

         

    def main(self):
    
        text_header = (u"Fuel %s setup "
            u"UP / DOWN / PAGE UP / PAGE DOWN scroll.  F8 exits."
            % version)
        text_footer = (u"Status messages go here.")
    
        blank = urwid.Divider()

        #Prepare submodules
        loader = Loader(self)
        self.children, self.choices = loader.load_modules(module_dir="./modules")
        if len(self.children) == 0:
          import sys
          sys.exit(1)

        #End prep
        menufill = urwid.Filler(self.menu(u'Menu', self.choices), 'top', 40)
        self.menubox = urwid.BoxAdapter(menufill, 40)


        child = self.children[0]
        self.childpage = child.screenUI()
        self.childfill = urwid.Filler(self.childpage, 'top', 22)
        self.childbox = urwid.BoxAdapter(self.childfill, 22)
        self.cols = urwid.Columns([
                ('fixed', 20, urwid.Pile([
                    urwid.AttrMap(self.menubox, 'bright'),
                    urwid.Divider(" ")])),
                ('weight', 3, urwid.Pile([
                    urwid.Divider(" "),
                    self.childbox,
                    urwid.Divider(" ")]))
                ], 3)
    
        self.header = urwid.AttrWrap(urwid.Text(text_header), 'header')
        self.footer = urwid.AttrWrap(urwid.Text(text_footer), 'footer')
        self.listwalker = urwid.SimpleListWalker([self.cols])
        #self.listwalker = urwid.TreeWalker([self.cols])
        self.listbox = urwid.ListBox(self.listwalker)
        #listbox = urwid.ListBox(urwid.SimpleListWalker(listbox_content))
    
        #frame = urwid.Frame(urwid.AttrWrap(cols, 'background'), header=header, footer=footer)
        #frame = urwid.Frame(urwid.AttrWrap(cols, 'body'), header=header, footer=footer)
        self.frame = urwid.Frame(urwid.AttrWrap(self.listbox, 'body'), header=self.header, footer=self.footer)
    
        palette = [
            ('body','black','light gray', 'standout'),
            ('reverse','light gray','black'),
            ('header','white','dark red', 'bold'),
            ('important','dark blue','light gray',('standout','underline')),
            ('editfc','white', 'dark blue', 'bold'),
            ('editbx','light gray', 'dark blue'),
            ('editcp','black','light gray', 'standout'),
            ('bright','dark gray','light gray', ('bold','standout')),
            ('buttn','black','dark cyan'),
            ('buttnf','white','dark blue','bold'),
            ('light gray','white', 'light gray','bold'),
            ('red','dark red','light gray','bold'),
            ('black','black','black','bold'),
            ]
    
    
        # use appropriate Screen class
        if urwid.web_display.is_web_request():
            self.screen = urwid.web_display.Screen()
        else:
            self.screen = urwid.raw_display.Screen()
    
        def unhandled(key):
            if key == 'f8':
                raise urwid.ExitMainLoop()
    
        self.mainloop= urwid.MainLoop(self.frame, palette, self.screen,
            unhandled_input=unhandled)
        self.mainloop.run()
    
    def exit_program(self, button):
        raise urwid.ExitMainLoop()


def setup():
    urwid.web_display.set_preferences("Fuel Setup")
    # try to handle short web requests quickly
    if urwid.web_display.handle_short_request():
         return
    fm = FuelSetup()
    

if '__main__'==__name__ or urwid.web_display.is_web_request():
    if urwid.VERSION < (1,1,0):
      print "This program requires urwid 1.1.0 or greater."
    setup()

