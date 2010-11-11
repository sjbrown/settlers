#! /usr/bin/env python
'''
server
'''

import sys
from pprint import pprint

from twisted.spread import pb
from twisted.spread.pb import DeadReferenceError
from twisted.cred import checkers, portal
from zope.interface import implements
import catan
import events
import network

DEBUG = True

#------------------------------------------------------------------------------
def PostMortem(fatalEvent, reactor):
    print "\n\nFATAL EVENT.  STOPPING REACTOR"
    reactor.stop()
    print 'Shared Objects at the time of the fatal event:'
    pprint( sharedObjectRegistry )


#------------------------------------------------------------------------------
class NoTickEventManager(events.EventManager):
    '''This subclass of EventManager doesn't wait for a Tick event before
    it starts consuming its event queue.  The server module doesn't have
    a CPUSpinnerController, so Ticks will not get generated.
    '''
    def __init__(self):
        events.EventManager.__init__(self)
        self._lock = False
    def post(self, event):
        self.eventQueue.append(event)
        #print 'ev q is', self.eventQueue, 'lock is', self._lock
        if not self._lock:
            self._lock = True
            #print 'consuming queue'
            self.actuallyUpdateListeners()
            self.consumeEventQueue()
            self._lock = False


#------------------------------------------------------------------------------
class TimerController:
    """A controller that sends an event every second"""
    def __init__(self, reactor):
        events.registerListener( self )

        self.reactor = reactor
        self.numClients = 0

    #-----------------------------------------------------------------------
    def NotifyApplicationStarted( self ):
        self.reactor.callLater( 1, self.Tick )

    #-----------------------------------------------------------------------
    def Tick(self):
        if self.numClients == 0:
            return

        events.post('SecondEvent')
        events.post('Tick')
        self.reactor.callLater( 5, self.Tick ) # repeat every 5 seconds

    #----------------------------------------------------------------------
    def onClientConnectEvent(self, mind, avatarID):
        # first client connected.  start the clock.
        self.numClients += 1
        if self.numClients == 1:
            self.Tick()

    #----------------------------------------------------------------------
    def onClientDisconnectEvent(self, avatarID):
        self.numClients -= 1

    #----------------------------------------------------------------------
    def onFatalEvent(self, event):
        PostMortem(event, self.reactor)


#------------------------------------------------------------------------------
class RegularAvatar(pb.IPerspective): pass
#class DisallowedAvatar(pb.IPerspective): pass
#------------------------------------------------------------------------------
class MyRealm:
    implements(portal.IRealm)
    def __init__(self):
        events.registerListener( self )
        # keep track of avatars that have been given out
        self.claimedAvatarIDs = []
        # we need to hold onto views so they don't get garbage collected
        self.clientViews = []
        # maps avatars to player(s) they control
        self.playersControlledByAvatar = {}

    #----------------------------------------------------------------------
    def requestAvatar(self, avatarID, mind, *interfaces):
        print ' v'*30
        print 'requesting avatar id: ', avatarID
        print ' ^'*30
        if pb.IPerspective not in interfaces:
            print 'TWISTED FAILURE'
            raise NotImplementedError
        avatarClass = RegularAvatar
        if avatarID in self.claimedAvatarIDs:
            #avatarClass = DisallowedAvatar
            raise Exception( 'Another client is already connected'
                             ' to this avatar (%s)' % avatarID )

        self.claimedAvatarIDs.append(avatarID)
        events.post('ClientConnectEvent', mind, avatarID)

        # TODO: this should be ok when avatarID is checkers.ANONYMOUS
        if avatarID not in self.playersControlledByAvatar:
            self.playersControlledByAvatar[avatarID] = []
        view = NetworkClientView(avatarID, mind)
        controller = NetworkClientController(avatarID,
                                             self)
        self.clientViews.append(view)
        return avatarClass, controller, controller.clientDisconnect

    #----------------------------------------------------------------------
    def knownPlayers(self):
        allPlayers = []
        for pList in self.playersControlledByAvatar.values():
            allPlayers.extend(pList)
        return allPlayers

    #----------------------------------------------------------------------
    def onClientDisconnectEvent(self, avatarID):
        print 'got cli disconnect'
        self.claimedAvatarIDs.remove(avatarID)
        removee = None
        for view in self.clientViews:
            if view.avatarID == avatarID:
                removee = view
        if removee:
            self.clientViews.remove(removee)

        print 'after disconnect, state is:'
        pprint (self.__dict__)


#------------------------------------------------------------------------------
class NetworkClientController(pb.Avatar):
    """We RECEIVE events from the CLIENT through this object
    There is an instance of NetworkClientController for each connected
    client.
    """
    def __init__(self, avatarID, realm):
        events.registerListener( self )
        self.avatarID = avatarID
        self.realm = realm

    #----------------------------------------------------------------------
    def clientDisconnect(self):
        '''When a client disconnect is detected, this method gets called
        '''
        events.post('ClientDisconnectEvent', self.avatarID)

    #----------------------------------------------------------------------
    def perspective_GetGameSync(self):
        """this is usually called when a client first connects or
        when they reconnect after a drop
        """
        print 'perspective_GetGameSync'
        game = sharedObjectRegistry.getGame()
        if game == None:
            print 'GetGameSync: game was none'
            raise Exception('Game should be set by this point')
        gameID = id( game )
        gameDict = game.getStateToCopy( sharedObjectRegistry )

        return [gameID, gameDict]
    
    #----------------------------------------------------------------------
    def perspective_GetObjectState(self, objectID):
        #print "request for object state", objectID
        if not sharedObjectRegistry.has_key( objectID ):
            print "No key on the server"
            return [0,0]
        obj = sharedObjectRegistry[objectID]
        print 'getting state for object', obj
        print 'my registry is '
        pprint(sharedObjectRegistry)
        objDict = obj.getStateToCopy( sharedObjectRegistry )

        return [objectID, objDict]
    
    #----------------------------------------------------------------------
    def perspective_DebugInfo(self):
        if DEBUG:
            from pprint import pformat
            return ('Debug Info\n' +
                    pformat(events.interestingHistory()[-5:]) +
                    '\n\nEvent Queue:\n' +
                    pformat(events._eventManager.eventQueue)
                    )

    #----------------------------------------------------------------------
    def perspective_EventOverNetwork(self, event):
        #if isinstance(event, network.CopyableCharactorPlaceRequest):
        #    try:
        #        player = sharedObjectRegistry[event.playerID]
        #    except KeyError, ex:
        #        events.post('FatalEvent', ex)
        #        raise
        #    pName = player.name
        #    if pName not in self.PlayersIControl():
        #        print 'i do not control', player
        #        print 'see?', self.PlayersIControl()
        #        print 'so i will ignore', event
        #        return
        #    try:
        #        charactor = sharedObjectRegistry[event.charactorID]
        #        sector = sharedObjectRegistry[event.sectorID]
        #    except KeyError, ex:
        #        events.post('FatalEvent', ex)
        #        raise
        #    ev = CharactorPlaceRequest( player, charactor, sector )
        #elif isinstance(event, network.CopyableCharactorMoveRequest):
        #    try:
        #        player = sharedObjectRegistry[event.playerID]
        #    except KeyError, ex:
        #        events.post('FatalEvent', ex)
        #        raise
        #    pName = player.name
        #    if pName not in self.PlayersIControl():
        #        return
        #    try:
        #        charactor = sharedObjectRegistry[event.charactorID]
        #    except KeyError, ex:
        #        print 'sharedObjs did not have key:', ex
        #        print 'current sharedObjs:', sharedObjectRegistry
        #        print 'Did a client try to poison me?'
        #        events.post('FatalEvent', ex)
        #        raise
        #    direction = event.direction
        #    ev = CharactorMoveRequest(player, charactor, direction)

        print 'event', event
        print 'event.name', event.name
        if event.name == 'PlayerJoinRequest':
            pName = event.playerName
            print 'got player join req.  known players:', self.realm.knownPlayers()
            if pName in self.realm.knownPlayers():
                print 'this player %s has already joined' % pName
                return 'this player %s has already joined' % pName
            self.ControlPlayer(pName)
            humanPlayer = catan.HumanPlayer(pName)
            ev = events.makeEventFromString('PlayerJoin', humanPlayer)
            events.post(ev)
        elif event.name == 'FillWithCPUPlayersRequest':
            from cpu_player_minimal import CPUPlayer
            events.post('PlayerJoin', CPUPlayer(1))
            events.post('PlayerJoin', CPUPlayer(2))
            events.post('PlayerJoin', CPUPlayer(3))
        else:
            ev = event
            events.post(ev)


        return 1

    #----------------------------------------------------------------------
    def PlayersIControl(self):
        return self.realm.playersControlledByAvatar[self.avatarID]

    #----------------------------------------------------------------------
    def ControlPlayer(self, playerName):
        '''Note: this modifies self.realm.playersControlledByAvatar'''
        players = self.PlayersIControl()
        players.append(playerName)
        
    #----------------------------------------------------------------------
    def onGameStartedEvent(self, event):
        self.game = event.game


#------------------------------------------------------------------------------
class TextLogView(object):
    def __init__(self, fp):
        events.registerListener( self )
        self.fp = fp

    #----------------------------------------------------------------------
    def notify(self, event):
        if event.name in ['Tick', 'Second']:
            return

        self.fp.write('TEXTLOG <')
        self.fp.write('event: %s' % event)
        self.fp.write('\n')


#------------------------------------------------------------------------------
class NetworkClientView(object):
    """We SEND events to the CLIENT through this object"""
    def __init__(self, avatarID, client):
        print "\nADDING CLIENT", client

        events.registerListener( self )

        self.avatarID = avatarID
        self.client = client

    #----------------------------------------------------------------------
    def RemoteCallError(self, failure):
        from twisted.internet.error import ConnectionLost
        #trap ensures that the rest will happen only 
        #if the failure was ConnectionLost
        failure.trap(ConnectionLost)
        self.HandleFailure(self.client)
        return failure

    #----------------------------------------------------------------------
    def HandleFailure(self):
        print "Failing Client", self.client

    #----------------------------------------------------------------------
    def RemoteCall( self, fnName, *args):
        try:
            remoteCall = self.client.callRemote(fnName, *args)
            remoteCall.addErrback(self.RemoteCallError)
        except DeadReferenceError:
            self.HandleFailure()

    #----------------------------------------------------------------------
    def EventThatShouldBeSent(self, ev):
        #don't send events that aren't Copyable
        if not isinstance( ev, pb.Copyable ):
            evName = ev.name
            copyableClsName = "Copyable"+evName
            if not hasattr( network, copyableClsName ):
                return None
            copyableClass = getattr( network, copyableClsName )
            ev = copyableClass( ev, sharedObjectRegistry )

        if ev.name not in network.serverToClientEvents:
            print 'SERVER NOT SENDING: %s (not in serverToClientEvents)' % ev
            return None

        return ev

    #----------------------------------------------------------------------
    def Notify(self, event):
        #NOTE: this is very "chatty".  We could restrict 
        #      the number of clients notified in the future

        ev = self.EventThatShouldBeSent(event)
        if not ev:
            return

        print "\n====server===sending: ", str(ev), 'to',
        print self.avatarID, '(', self.client, ')'
        self.RemoteCall( "ServerEvent", ev )


#------------------------------------------------------------------------------
class Model(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.gameKey = None

    def __setitem__(self, key, val):
        print 'setting', key, val
        dict.__setitem__(self, key, val)
        if isinstance(val, catan.Game):
            self.gameKey = key

    def getGame(self):
        return self[self.gameKey]

sharedObjectRegistry = None
#------------------------------------------------------------------------------
def main():
    global sharedObjectRegistry
    from twisted.internet import reactor
    evManager = NoTickEventManager()
    events._eventManager = evManager
    sharedObjectRegistry = Model()

    logfile = sys.stdout
    log = TextLogView(logfile)
    timer = TimerController(reactor)
    catan.init()
    sharedObjectRegistry[id(catan.game)] = catan.game

    #factory = pb.PBServerFactory(clientController)
    #reactor.listenTCP( 8000, factory )

    realm = MyRealm()
    portl = portal.Portal(realm)
    checker = checkers.InMemoryUsernamePasswordDatabaseDontUse(
                                                           user1='pass1',
                                                           user2='pass1')
    portl.registerChecker(checker)
    reactor.listenTCP(8000, pb.PBServerFactory(portl))

    reactor.run()

if __name__ == "__main__":
    print 'starting server...'
    main()

