twisted traits, networked traits using twisted
**********************************************

twisted traits (a.k.a. txtraits), is a small library for networking of
`Enthought Traits <http://code.enthought.com/projects/traits/>`_. The
notification, validation, and auto-generated GUI views of traits are
extended across a network through the use of `twisted.spread
<http://twistedmatrix.com>`_.

What works
==========

* bi-directional getting, setting, and notification of trait changes
  and events for simple trait attributes (e.g. int, float, tuples,
  etc).
* Support for multiple simultaneous mirrors of a HasTraits instance.

What does not work (yet)
========================

* Automatic mirroring of trait attributributes such as HasTraits
  instances and anything else that cannot be serialized by
  twisted.spread.

* Read only traits, DelegatesTo, or PrototypedFrom.

LICENSE
=======

txtraits is available under the MIT license (see LICENSE.txt).

To run the examples
===================

simple
------

This transmits a small amount of information using a twitsted .tac
file to serve the application.

::

  cd examples
  twistd -ny simple_server.tac &
  twistd -n --pidfile=client.pid -y simple_client.tac


wx using translucent proxying
-----------------------------

This creates a translucent proxy of a server object.

::

  cd examples
  python wx_server.py &
  python wx_client_translucent_proxy.py

wx using mirroring
------------------

This mirrors a server object. A translucent mirror is used under the
hood to implement the mirror functionality.

::

  cd examples
  python wx_server.py &
  python wx_client_mirror.py
