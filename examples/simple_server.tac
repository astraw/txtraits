# -*- mode: Python;-*-

# You can run this .tac file directly with:
#    twistd -ny simple_server.tac

from twisted.spread import pb
from twisted.application.internet import TCPServer
from twisted.application.service import Application
import txtraits
import enthought.traits.api as traits

hub = txtraits.TraitsNetHub()

class Person(traits.HasTraits):
    name = traits.String
    age = traits.Int
person = Person(name='Alice',age=38)
hub.share(person,name='person1')

hub.share(Person(name='Bob',age=13))

serverfactory = pb.PBServerFactory(hub)
application = Application("TraitsNetHub")
hubServerService = TCPServer(8789, serverfactory)
hubServerService.setServiceParent(application)
