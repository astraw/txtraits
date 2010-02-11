from twisted.spread import pb
import enthought.traits.api as traits
import txtraits
import wx
from enthought.traits.ui.api import View, Item, Group

from twisted.internet import wxreactor
wxreactor.install()
from twisted.internet import reactor

class Doit(traits.HasTraits):
    age = traits.Int(20)
    person_proxy = traits.Any

    traits_view = View( Group( Item('age')))

    def __init__(self):
        self.person_proxy = None
        super(Doit,self).__init__()

    def _age_changed(self):
        if self.person_proxy is not None:
            d = self.person_proxy.proxy_set_async('age', self.age)

    def connect(self,local_hub,remote_server):
        d = local_hub.request_proxy(remote_server,'person')
        d.addCallback( self.on_got_proxy )

    def on_got_proxy(self,person_proxy):
        self.person_proxy = person_proxy
        d = self.person_proxy.proxy_get_async('age')
        d.addCallback( lambda x: self.set(age=x) )
        self.person_proxy.proxy_on_trait_change('age', self.on_remote_age_changed)

    def on_remote_age_changed(self, value):
        # TODO: the following setter should not trigger call to
        # set_async, since it came from remote side originally.
        self.age = value

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
