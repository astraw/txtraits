from twisted.spread import pb
import enthought.traits.api as traits
import txtraits
import wx
from enthought.traits.ui.api import View, Item, Group, ButtonEditor

from twisted.internet import wxreactor
wxreactor.install()
from twisted.internet import reactor

class Person(traits.HasTraits):
    name = traits.String
    age = traits.Int
    do_something = traits.Event

    traits_view = View( Group( Item('name'),
                               Item('age'),
                               Item('do_something',
                                    editor = ButtonEditor(label_value='do_something'))))

    def _do_something_fired(self):
        print 'something!'

if __name__ == '__main__':
    app = wx.App(False)
    frame = wx.Frame(None)
    frame.Show()
    reactor.registerWxApp(app)

    person = Person(name='Andrew',age=35)
    person.do_something = True
    person.do_something = True
    person.edit_traits( parent=frame, kind='subpanel' )

    hub = txtraits.TraitsNetHub()
    hub.share(person,name='person')

    reactor.listenTCP(5001, pb.PBServerFactory(hub))
    reactor.run()
