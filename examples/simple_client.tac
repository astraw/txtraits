# -*- mode: Python;-*-

# You can run this .tac file directly with:
#    twistd -n --pidfile client.pid -y simple_client.tac

from twisted.spread import pb
from twisted.application.internet import TCPClient
from twisted.application.service import Application
import txtraits
import enthought.traits.api as traits

def on_connect(local_hub,remote_server):
    """our local hub has connected to a remote hub"""

    # request the names of all shared traited instances
    d = local_hub.get_shared_names(remote_server)

    # add a callback to the deferred to make use of the names
    d.addCallback( on_received_shared_names, local_hub, remote_server )

def on_received_shared_names(remote_names,local_hub,remote_server):
    """we received a list of the names shared by a remote hub"""
    for remote_name in remote_names:
        print 'received name',remote_name

        # request a mirror of the remote traited object
        d = local_hub.request_mirror(remote_server,remote_name)

        # add a callback to make use of the mirror
        d.addCallback( on_received_mirror, remote_name )

def on_received_mirror(traited_instance_mirror, remote_name):
    """we received a mirror of a remote traited instance"""
    print 'traited_instance_mirror: %s'%remote_name
    for n in traited_instance_mirror.trait_names():
        if n in txtraits.ignore_remote_mirror_traits:
            continue
        value=getattr(traited_instance_mirror,n)
        print '  %s: %s'%(n, value)

hub = txtraits.TraitsNetHub()
clientfactory = pb.PBClientFactory()
d = clientfactory.getRootObject()
d.addCallback(hub.on_client_connect)
hub.add_on_remote_hub_connect_callback( on_connect )

application = Application("TraitsNetHub")
hubClientService = TCPClient("localhost", 8789, clientfactory)
hubClientService.setServiceParent(application)
