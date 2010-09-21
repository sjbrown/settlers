#SECURITY NOTE: anything in here can be created simply by sending the 
# class name over the network.  This is a potential vulnerability
# I wouldn't suggest letting any of these classes DO anything, especially
# things like file system access, or allocating huge amounts of memory

import logging
logging.basicConfig()

DEBUG = 1

if DEBUG:
    import traceback
    eventHistory = []
    def interestingHistory():
        return [ev for ev in eventHistory if ev.name not in
                ['Tick', 'KeyDown', 'MouseMotion']]

#------------------------------------------------------------------------------
class EventManager:
    """this object is responsible for coordinating most communication
    between the Model, View, and Controller."""
    def __init__(self):
        from weakref import WeakKeyDictionary
        self.listeners = WeakKeyDictionary()
        self.eventQueue= []
        self.listenersToAdd = []
        self.listenersToRemove = []

    #----------------------------------------------------------------------
    def registerListener( self, listener ):
        self.listenersToAdd.append(listener)

    #----------------------------------------------------------------------
    def actuallyUpdateListeners(self):
        for listener in self.listenersToAdd:
            self.listeners[ listener ] = 1
        for listener in self.listenersToRemove:
            if listener in self.listeners:
                del self.listeners[ listener ]

    #----------------------------------------------------------------------
    def unregisterListener( self, listener ):
        self.listenersToRemove.append(listener)
        
    #----------------------------------------------------------------------
    # NOTE: this production is not draw-friendly.
    def post( self, event ):
        if DEBUG:
            if event.name not in ['Tick', 'MouseMotion']:
                print 'ev posted', event
            # get the last three lines of code that got us here
            stack = traceback.extract_stack()[-6:-3]
            event.stack = stack
        self.eventQueue.append(event)
        if event.name == 'Tick':
            # Consume the event queue every Tick.
            self.actuallyUpdateListeners()
            self.consumeEventQueue()
        else:
            logging.debug( "     Message: " + event.name )

    #----------------------------------------------------------------------
    def deliverEvent(self, event, listener, methodName):
        attempt = [True]
        while attempt:
            attempt = [] # can be turned True while in pdb
            try:
                if hasattr(listener, methodName):
                    method = getattr(listener, methodName)
                    method(*event.args, **event.kwargs)
                elif hasattr(listener, 'notify'):
                    method = getattr(listener, 'notify')
                    method(event)
            except Exception, ex:
                import sys
                import pdb
                import traceback
                print '*'*20, 'EXCEPTION', '*'*20
                print 'To recover, make attempt true: attempt.append(1)'
                print 'To examine the traceback where the exception happened,'
                print 'run a postmortem: pdb.post_mortem(exc_info[2])'
                print ''
                exc_info = sys.exc_info()
                traceback.print_exception(*exc_info)
                # set attempt to True in pdb to recover
                pdb.set_trace()
                if not attempt:
                    raise

    #----------------------------------------------------------------------
    # NOTE: this consumption is not draw-friendly.
    def consumeEventQueue(self):
        print 'consuming'
        i = 0
        while i < len( self.eventQueue ):
            event = self.eventQueue[i]
            if DEBUG:
                eventHistory.append(event)
            methodName = 'on' + event.__class__.__name__
            for listener in self.listeners:
                # Note: a side effect of notifying the listener
                # could be that more events are put on the queue
                # or listeners could Register / Unregister
                self.deliverEvent(event, listener, methodName)
            i += 1
            if self.listenersToAdd:
                self.actuallyUpdateListeners()
        # all code paths that could possibly add more events to 
        # the eventQueue have been exhausted at this point, so 
        # it's safe to empty the queue
        self.eventQueue = []


_eventManager = EventManager()

def post(arg1, *extraArgs, **kwargs):
    if isinstance(arg1, Event):
        assert not extraArgs
        assert not kwargs
        post_eventObj(arg1)
    else:
        assert isinstance(arg1, str)
        post_stringEvent(arg1, extraArgs, kwargs)

def post_eventObj(ev):
    _eventManager.post(ev)

def post_stringEvent(arg1, extraArgs, kwargs):
    class AnonymousEvent(Event): pass
    AnonymousEvent.__name__ = arg1
    event = AnonymousEvent()
    event.name = arg1
    event.args = extraArgs
    event.kwargs = kwargs
    _eventManager.post(event)


def registerListener(listener):
    _eventManager.registerListener(listener)

def unregisterListener(listener):
    _eventManager.unregisterListener(listener)


class Event:
    """this is a superclass for any events that might be generated by an
    object and sent to the EventManager"""
    def __init__(self, *args, **kwargs):
        self.name = self.__class__.__name__
        self.args = args
        self.kwargs = kwargs
    def __str__(self):
        return '<%s %s>' % (self.name, id(self))
        

class Tick(Event):
    def __init__(self):
        Event.__init__(self)
        self.name = "Tick"

class Quit(Event):
    def __init__(self):
        Event.__init__(self)
        self.name = "Program Quit Event"


if __name__ == '__main__':

    class Printer(object):
        def onA(self, foo, bar):
            print 'A'
            post('C')
        def onB(self, foo, bar):
            print 'B'
        def onC(self):
            print 'C'

    class NotifyPrinter(object):
        def notify(self, event):
            print '\t\tNotify event', event

    p = Printer()
    np = NotifyPrinter()
    registerListener(p)
    registerListener(np)

    post(Tick())

    post('A', 'foo', 'bar')

    class B(Event): pass
    evB = B()
    evB.kwargs = dict(foo = 'foo', bar = 'bar')
    post(evB)

    post(Tick())
