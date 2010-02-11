from twisted.spread import pb
import enthought.traits.api as traits
import txtraits
import wx
from enthought.traits.ui.api import View, Item, Group, ButtonEditor

from twisted.internet import wxreactor
wxreactor.install()
from twisted.internet import reactor

class Doit(traits.HasTraits):
    person = traits.Instance( traits.HasTraits )
    button = traits.Event

    traits_view = View( Group( Item('person'),
                               Item('button',
                                    editor = ButtonEditor(label_value='button'))))

    def connect(self,local_hub,remote_server):
        d = local_hub.request_mirror(remote_server,'person')
        d.addCallback( self.on_got_mirror )

    def on_got_mirror(self,person):
        self.person = person

        self.person.on_trait_event( self.on_do_something, name='do_something' )

    def on_do_something(self):
        print 'something fired!'

    def _button_fired(self):
        print 'button pressed, firing event'
        self.person.do_something = True

if __name__ == '__main__':
    app = wx.App(False)
    frame = wx.Frame(None)
    frame.Show()
    reactor.registerWxApp(app)

    hub = txtraits.TraitsNetHub()
    doit = Doit()
    doit.edit_traits( parent=frame, kind='subpanel' )
    hub.add_on_remote_hub_connect_callback( doit.connect )
    reactor.registerWxApp(app)

    clientfactory = pb.PBClientFactory()
    d = clientfactory.getRootObject()
    d.addCallback(hub.register_with_remote_hub)
    reactor.connectTCP("localhost", 5001, clientfactory)
    reactor.run()
