from twisted.spread import pb
from twisted.internet import defer
import enthought.traits.api as traits
import enthought.traits.trait_handlers
import warnings
import platform, os

reserved_trait_names = ['trait_added','trait_modified']

class TraitValueError(ValueError):
    def __str__(self):
        result = ValueError.__str__(self)
        if hasattr(self,'trait_name'):
            result += ' for trait name %s'%(self.trait_name,)
        return result

class TraitsWriteOnlyEventError(ValueError):
    pass

class NoValue:
    pass
novalue = NoValue()

def is_event_trait(trait):
    # Delve into the traits implementation details to
    # determine if trait is an event.
    kind = trait.__getstate__()[0]
    EVENT_KIND=2
    return kind==EVENT_KIND

def get_trait_definition_for_trait_code(code,initial_value=novalue):
    if code=='an integer':
        trait_definition = traits.Int
    elif code=='a string':
        trait_definition = traits.String
    elif code=='a legal value':
        trait_definition = traits.Any
    elif code=='any value':
        trait_definition = traits.Any
    elif code=='an event':
        trait_definition = traits.Event
    else:
        raise TraitValueError('unknown trait definition code "%s"'%code)
    if not isinstance(initial_value,NoValue):
        trait_definition = trait_definition( initial_value )
    return trait_definition

def get_trait_code_for_trait_definition(trait_definition):
    if is_event_trait(trait_definition):
        return 'an event'
    info = trait_definition.info()
    assert isinstance(info,basestring)
    code = info
    return code

class RemoteHasTraitsProxy(traits.HasTraits):
    """translucent proxy"""
    _local_hub = traits.Any
    _remote_server = traits.Any
    _remote_name = traits.String
    _initial_traits = traits.Dict
    _callback_map = traits.Dict

    def proxy_trait_names(self):
        for n in self._initial_traits.keys():
            yield n

    def proxy_get_trait_definition_code_and_value_async(self,trait_name):
        return self._remote_server.callRemote('get_trait_definition_code_and_value',
                                              self._remote_name,trait_name)

    def proxy_get_async(self,trait_name):
        return self._remote_server.callRemote('get_value',
                                              self._remote_name,trait_name)

    def proxy_set_async(self,trait_name,value):
        return self._remote_server.callRemote('set_value',
                                              self._remote_name,trait_name,value)

    def proxy_on_trait_change(self, trait_name, callback):
        # generate a string to pass over the network to identify our callback
        key = self._local_hub.register_callback(callback)
        d = self._remote_server.callRemote('on_trait_change',self._local_hub,
                                           self._remote_name,trait_name,key)

    def proxy_on_trait_event(self, trait_name, callback):
        # generate a string to pass over the network to identify our callback
        key = self._local_hub.register_callback(callback)
        d = self._remote_server.callRemote('on_trait_event',self._local_hub,
                                           self._remote_name,trait_name,key)

class MirrorAttrHelper:
    """helper class for each trait of a mirrored HasTrait instance"""
    def __init__(self,parent,attr_name,initial_value=novalue):
        self.parent=parent
        self.attr_name = attr_name
        self.initial_value = initial_value
        d = self.parent.proxy_get_trait_definition_code_and_value_async(self.attr_name)
        d.addCallback( self._on_set_trait_definition_code_and_value )
        self._setup_deferred = d

        # the remote triggered the event, which we don't want to propagate back
        # XXX TODO FIXME: should find better unique solution
        self._no_return_event = hash('no return %s %d'%
                                     (platform.node(), os.getpid()))

        # we triggered a remote event, which we don't want to receive again
        # XXX TODO FIXME: should find better unique solution
        self._no_receive_event = hash('no receive %s %d'%
                                      (platform.node(), os.getpid()))

    def _on_set_trait_definition_code_and_value(self, input ):
        trait_code, value = input
        try:
            trait_definition = get_trait_definition_for_trait_code(
                trait_code,initial_value=self.initial_value)
        except TraitValueError,err:
            err.trait_name = self.attr_name
            raise
        self.parent.add_trait( self.attr_name, trait_definition )

        if isinstance(trait_definition, traits.Event):
            # request notification of future changes to trait
            self.parent.proxy_on_trait_event(self.attr_name,
                                             self.remote_fired)

            # send any local changes in future to remote
            self.parent.on_trait_event( self.local_fired,
                                        self.attr_name )
        else:
            # request notification of future changes to trait
            self.parent.proxy_on_trait_change(self.attr_name,
                                              self.remote_changed)

            # send any local changes in future to remote
            self.parent.on_trait_change( self.local_changed,
                                         self.attr_name )

            self.parent.trait_set( **{self.attr_name:value} )

    def remote_changed(self,value):
        self.remote_shadow = value
        setattr(self.parent, self.attr_name, value)

    def local_changed(self, object, attr_name, old_value, new_value):
        assert object is self.parent
        assert attr_name == self.attr_name
        if hasattr(self,'remote_shadow') and self.remote_shadow == new_value:
            return
        self.parent.proxy_set_async(attr_name,new_value)

    def remote_fired(self,value):
        self.remote_shadow = value
        if value == self._no_receive_event:
            return
        setattr(self.parent, self.attr_name, self._no_return_event )

    def local_fired(self, object, attr_name, old_value, new_value):
        assert object is self.parent
        assert attr_name == self.attr_name
        if new_value ==  self._no_return_event:
            return
        self.parent.proxy_set_async(attr_name,self._no_receive_event)

    def get_setup_deferred(self):
        return self._setup_deferred

class RemoteMirror(RemoteHasTraitsProxy):
    """transparent proxy, acting as a mirror of a remote traited instance"""
    construction_deferred = traits.Any
    def __init__(self,*args,**kwargs):
        super(RemoteMirror,self).__init__(*args,**kwargs)
        dlist = []
        for attr_name in self._initial_traits.keys():

            attr_value = self._initial_traits.get(attr_name,NoValue())

            # create out helper
            mirror_attr_helper = MirrorAttrHelper(self,attr_name,
                                                  initial_value=attr_value)

            # get Deferred for setup of trait
            d = mirror_attr_helper.get_setup_deferred()

            # keep track of population of traits with values
            dlist.append(d)
        self.construction_deferred = defer.DeferredList(dlist)

    def default_traits_view(self):
        import enthought.traits.ui.api as traits_ui

        items = [ traits_ui.Item( name )
                  for name in self._initial_traits.keys() ]
        return traits_ui.View(traits_ui.Group(*items))

ignore_remote_mirror_traits = [n for n in RemoteMirror().trait_names()]

def get_trait_value(traited_instance,trait_name):
    trait = traited_instance.trait(trait_name)
    if is_event_trait(trait):
        raise TraitsWriteOnlyEventError("the trait '%s' is an 'event', "
                                        "which is write only"%trait_name)
    result = getattr(traited_instance,trait_name)
    return result

class TraitsNetHub(pb.Root):
    def __init__(self):
        self.remote_servers = []
        self.shared = {}
        self.connect_cbs = []
        self.disconnect_cbs = []
        self.callbacks = {}

    def _generate_key(self):
        if not hasattr(self,'_count'):
            self._count = 0
        else:
            self._count += 1
        key = 'key%d'%self._count
        return key

    def register_callback(self,callback):
        key = self._generate_key()
        self.callbacks[key] = callback
        return key

    def convert_to_wire(self,orig):
        if isinstance(orig,enthought.traits.trait_handlers.TraitListObject):
            result = list(orig)
        ## elif isinstance(orig,basestring):
        ##     result = orig
        ## elif isinstance(orig,int):
        ##     result = orig
        ## elif isinstance(orig, NoValue):
        ##     result = '<no value>'
        elif isinstance(orig,traits.HasTraits):
            # don't let traits try to outsmart twisted
            raise TraitValueError('could not convert value %s (type %s) '
                                      'to wire' % (orig,type(orig)))
        else:
            result = orig
        ## else:
        ##     raise ValueError('could not convert value %s (type %s) to wire' %
        ##                      (orig,type(orig)))
        return result

    def remote_get_trait_definition_code_and_value(self,instance_name,trait_name):
        traited_instance = self.shared[instance_name]
        trait_definition = traited_instance.trait( trait_name )
        trait_definition_code = get_trait_code_for_trait_definition(trait_definition)
        try:
            wire_value = self.remote_get_value(instance_name,trait_name)
        except TraitValueError,err:
            err.trait_name = trait_name
            raise
        return trait_definition_code, wire_value

    def remote_get_value(self,instance_name,trait_name):
        traited_instance = self.shared[instance_name]
        trait = traited_instance.trait(trait_name)
        if is_event_trait(trait):
            wire_value = True # fire event
        else:
            orig_value = getattr(traited_instance,trait_name)
            wire_value = self.convert_to_wire(orig_value)
        return wire_value

    def remote_set_value(self,instance_name,trait_name,wire_value):
        traited_instance = self.shared[instance_name]
        setattr(traited_instance,trait_name,wire_value)

    def remote_on_trait_change(self, remote_hub, instance_name, trait_name, key):
        traited_instance = self.shared[instance_name]
        def callback_wrapper(newvalue):
            remote_hub.callRemote('callback',key,newvalue)
        traited_instance.on_trait_change( callback_wrapper, trait_name)

    def remote_on_trait_event(self, remote_hub, instance_name, trait_name, key):
        traited_instance = self.shared[instance_name]
        def callback_wrapper(newvalue):
            remote_hub.callRemote('callback',key,newvalue)
        traited_instance.on_trait_event( callback_wrapper, trait_name)

    def remote_callback(self,key,newvalue):
        self.callbacks[key](newvalue)

    def remote_get_attr_names_and_values(self, instance_name ):
        traited_instance = self.shared[instance_name]
        result = {}
        for n in traited_instance.trait_names():
            if n in reserved_trait_names:
                continue
            try:
                result[n] = get_trait_value(traited_instance,n)
            except TraitsWriteOnlyEventError,err:
                result[n] = 0 # dummy value for event
        return result

    def share(self,traited_instance,name=None):
        assert isinstance(traited_instance,traits.HasTraits)
        if name is None:
            name = self._generate_key()
        assert isinstance(name,basestring),'name "%s" is not a string'%name
        assert name not in self.shared,'already sharing name "%s"'%name
        self.shared[name] = traited_instance

    def get_shared_names(self,remote_server):
        d = remote_server.callRemote("get_shared_names")
        return d

    def remote_get_shared_names(self):
        return self.shared.keys()

    def request_proxy(self,remote_server,remote_traited_name):
        assert remote_server in self.remote_servers
        d = remote_server.callRemote("get_attr_names_and_values",
                                     remote_traited_name)
        d.addCallback(self.build_proxy, (remote_server,remote_traited_name))
        return d

    def build_proxy(self,attr_names_and_values,remote_info):
        remote_server,remote_traited_name = remote_info
        proxy = RemoteHasTraitsProxy( _local_hub = self,
                                      _remote_server = remote_server,
                                      _remote_name = remote_traited_name,
                                      _initial_traits = attr_names_and_values )
        return proxy

    def request_mirror(self,
                       remote_server,
                       remote_traited_name,
                       exclude_attrs=None,
                       exclude_private=True):
        assert remote_server in self.remote_servers
        d = remote_server.callRemote("get_attr_names_and_values",
                                     remote_traited_name)
        if exclude_attrs is None:
            exclude_attrs = []
        info = (remote_server, remote_traited_name,
                exclude_attrs, exclude_private)
        d.addCallback(self.build_mirror, info )
        return d

    def build_mirror(self,attr_names_and_values,info):
        (remote_server, remote_traited_name, \
         exclude_attrs, exclude_private) = info

        for attr in exclude_attrs:
            if attr in attr_names_and_values:
                del attr_names_and_values[attr]
            else:
                warnings.warn('requested exclusion of attr "%s", but it is '
                              'not present' % attr )

        if exclude_private:
            for attr in attr_names_and_values.keys():
                if attr.startswith('_'):
                    del attr_names_and_values[attr]
        mirror = RemoteMirror( _local_hub = self,
                               _remote_server = remote_server,
                               _remote_name = remote_traited_name,
                               _initial_traits = attr_names_and_values,
                               )
        d = mirror.construction_deferred
        d.addCallback(self.return_mirror,mirror)
        return d

    def return_mirror(self,results,mirror):
        return mirror

    def remote_register_hub(self,remote,initial=True):
        assert remote not in self.remote_servers
        self.remote_servers.append(remote)
        remote.notifyOnDisconnect(self.unregister_hub)
        if initial:
            remote.callRemote('register_hub',self,initial=False)
        for cb in self.connect_cbs:
            cb(self,remote)

    def register_with_remote_hub(self,remote_client_root):
        d = remote_client_root.callRemote('register_hub',self)
        return d

    def unregister_hub(self,remote_server):
        self.remote_servers.remove(remote_server)
        for cb in self.disconnect_cbs:
            cb(self,remote_server)

    def add_on_remote_hub_connect_callback( self, cb ):
        self.connect_cbs.append( cb )

    def add_on_remote_hub_disconnect_callback( self, cb ):
        self.disconnect_cbs.append( cb )
