import sys, os, time, gc

from cStringIO import StringIO
from zope.interface import implements, Interface

from twisted.python.versions import Version
from twisted.trial import unittest
from twisted.spread import pb, util, publish, jelly
from twisted.internet import protocol, main, reactor
from twisted.internet.error import ConnectionRefusedError
from twisted.internet.defer import Deferred, gatherResults, succeed
from twisted.protocols.policies import WrappingFactory
from twisted.python import failure, log
from twisted.cred.error import UnauthorizedLogin, UnhandledCredentials
from twisted.cred import portal, checkers, credentials
import enthought.traits.api as traits
import txtraits

class IOPump:
    """
    Utility to pump data between clients and servers for protocol testing.

    Perhaps this is a utility worthy of being in protocol.py?
    """
    def __init__(self, client, server, clientIO, serverIO):
        self.client = client
        self.server = server
        self.clientIO = clientIO
        self.serverIO = serverIO

    def flush(self):
        """
        Pump until there is no more input or output. This does not run any
        timers, so don't use it with any code that calls reactor.callLater.
        """
        # failsafe timeout
        timeout = time.time() + 5
        while self.pump():
            if time.time() > timeout:
                return

    def pump(self):
        """
        Move data back and forth.

        Returns whether any data was moved.
        """
        self.clientIO.seek(0)
        self.serverIO.seek(0)
        cData = self.clientIO.read()
        sData = self.serverIO.read()
        self.clientIO.seek(0)
        self.serverIO.seek(0)
        self.clientIO.truncate()
        self.serverIO.truncate()
        self.client.transport._checkProducer()
        self.server.transport._checkProducer()
        for byte in cData:
            self.server.dataReceived(byte)
        for byte in sData:
            self.client.dataReceived(byte)
        if cData or sData:
            return 1
        else:
            return 0

class DummyRealm(object):
    implements(portal.IRealm)

    def requestAvatar(self, avatarId, mind, *interfaces):
        for iface in interfaces:
            if iface is pb.IPerspective:
                return iface, DummyPerspective(avatarId), lambda: None

def connectedServerAndClient():
    """
    Returns a 3-tuple: (client, server, pump).
    """
    # from twisted.test.test_pb.py
    clientBroker = pb.Broker()
    checker = checkers.InMemoryUsernamePasswordDatabaseDontUse(guest='guest')
    factory = pb.PBServerFactory(portal.Portal(DummyRealm(), [checker]))
    serverBroker = factory.buildProtocol(('127.0.0.1',))

    clientTransport = StringIO()
    serverTransport = StringIO()
    clientBroker.makeConnection(protocol.FileWrapper(clientTransport))
    serverBroker.makeConnection(protocol.FileWrapper(serverTransport))
    pump = IOPump(clientBroker, serverBroker, clientTransport, serverTransport)
    # Challenge-response authentication:
    pump.flush()
    return clientBroker, serverBroker, pump

def test_lowlevel_hub():
    c, s, pump = connectedServerAndClient()

    class A(traits.HasTraits):
        name = traits.String
        age = traits.Int

    server_local = txtraits.TraitsNetHub()
    s.setNameForLocal('hub',server_local)

    server_local.share(A(name='Alice',age=38),name='person')

    # get translucent object from server
    server_remote = c.remoteForName('hub')

    def check_age(args):
        assert args==38
    d = server_remote.callRemote('get_value','person','age')
    d.addCallback(check_age)
    pump.pump()
    pump.pump()
    pump.pump()
    d = server_remote.callRemote('get_value','person','name')
    def check_name(args):
        assert args=='Alice'
    d.addCallback(check_name)
    pump.pump()
    pump.pump()

def test_mirror():
    c, s, pump = connectedServerAndClient()

    class A(traits.HasTraits):
        name = traits.String
        age = traits.Int

    server_local = txtraits.TraitsNetHub()
    s.setNameForLocal('hub',server_local)

    server_local.share(A(name='Alice',age=38),name='person')

    server_remote = c.remoteForName('hub')

    # now, connect to our server
    hub = txtraits.TraitsNetHub()
    hub.remote_register_hub( server_remote )
    d = hub.request_mirror( server_remote, 'person' )

    # a variable to pass the result out of the callback
    status = {'success':False}

    # the actual test callback
    def on_got_mirror(person,st):
        assert person.age==38
        assert person.name=='Alice'
        st['success']=True

    # schedule the callback
    d.addCallback( on_got_mirror, status )

    # pump twisted
    pump.pump()
    pump.pump()

    pump.pump()
    pump.pump()

    # ensure the test was called (successfully)
    if not status['success']:
        raise RuntimeError('mirror validation did not run')
