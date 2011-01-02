import sys
import time
import network
from twisted.spread import pb
from twisted.internet.selectreactor import SelectReactor
from twisted.internet.main import installReactor
from twisted.cred import credentials
import events
import catan
import pygameview

serverHost, serverPort = 'localhost', 8000
avatarID = None

#------------------------------------------------------------------------------
class NetworkServerView(pb.Root):
    """We SEND events to the server through this object"""
    STATE_PREPARING = 0
    STATE_CONNECTING = 1
    STATE_CONNECTED = 2
    STATE_DISCONNECTING = 3
    STATE_DISCONNECTED = 4

    #----------------------------------------------------------------------
    def __init__(self, sharedObjectRegistry):
        events.registerListener( self )

        self.pbClientFactory = pb.PBClientFactory()
        self.state = NetworkServerView.STATE_PREPARING
        self.reactor = None
        self.server = None

        self.sharedObjs = sharedObjectRegistry

    #----------------------------------------------------------------------
    def AttemptConnection(self):
        print "attempting a connection to", serverHost, serverPort
        self.state = NetworkServerView.STATE_CONNECTING
        if self.reactor:
            self.reactor.stop()
            self.PumpReactor()
        else:
            self.reactor = SelectReactor()
            installReactor(self.reactor)
        connection = self.reactor.connectTCP(serverHost, serverPort,
                                             self.pbClientFactory)
        # TODO: make this anonymous login()
        #deferred = self.pbClientFactory.login(credentials.Anonymous())
        userCred = credentials.UsernamePassword(avatarID, 'pass1')
        controller = NetworkServerController()
        deferred = self.pbClientFactory.login(userCred, client=controller)
        deferred.addCallback(self.Connected)
        deferred.addErrback(self.ConnectFailed)
        self.reactor.startRunning()

    #----------------------------------------------------------------------
    def Disconnect(self):
        print "disconnecting"
        if not self.reactor:
            return
        print 'stopping the reactor'
        self.reactor.stop()
        self.PumpReactor()
        self.state = NetworkServerView.STATE_DISCONNECTING

    #----------------------------------------------------------------------
    def Connected(self, server):
        print "CONNECTED"
        self.server = server
        self.state = NetworkServerView.STATE_CONNECTED
        events.post('ServerConnectEvent', server)

    #----------------------------------------------------------------------
    def ConnectFailed(self, server):
        print "CONNECTION FAILED"
        print server
        print 'quitting'
        events.post( events.QuitEvent() )
        #self.state = NetworkServerView.STATE_PREPARING
        self.state = NetworkServerView.STATE_DISCONNECTED

    #----------------------------------------------------------------------
    def PumpReactor(self):
        self.reactor.runUntilCurrent()
        self.reactor.doIteration(0)

    #----------------------------------------------------------------------
    def onTick(self):
        if self.state == NetworkServerView.STATE_PREPARING:
            self.AttemptConnection()
        elif self.state in [NetworkServerView.STATE_CONNECTED,
                            NetworkServerView.STATE_DISCONNECTING,
                            NetworkServerView.STATE_CONNECTING]:
            self.PumpReactor()
        return

    #----------------------------------------------------------------------
    def onQuit(self):
        self.Disconnect()

    #----------------------------------------------------------------------
    def notify(self, event):
        ev = event
        if not isinstance( event, pb.Copyable ):
            evName = event.__class__.__name__
            copyableClsName = "Copyable"+evName
            if not hasattr( network, copyableClsName ):
                return
            copyableClass = getattr( network, copyableClsName )
            #NOTE, never even construct an instance of an event that
            # is serverToClient, as a side effect is often adding a
            # key to the registry with the local id().
            if ev.name not in network.clientToServerEvents:
                print "CLIENT NOT CREATING: " + str(copyableClsName)
                return
            print 'creating instance of copyable class', copyableClsName
            ev = copyableClass( event, self.sharedObjs )

        if ev.name not in network.clientToServerEvents:
            print "CLIENT NOT SENDING: " + str(ev)
            return

        if self.server:
            print " ====   Client sending", str(ev)
            remoteCall = self.server.callRemote("EventOverNetwork", ev)
        else:
            print " =--= Cannot send while disconnected:", str(ev)


#------------------------------------------------------------------------------
class NetworkServerController(pb.Referenceable):
    """We RECEIVE events from the server through this object"""
    def __init__(self):
        events.registerListener( self )

    #--------------------------------------------------------------------------
    def remote_ServerEvent(self, event):
        print " ====  GOT AN EVENT FROM SERVER:", str(event)
        events.post( event )
        return 1

    #--------------------------------------------------------------------------
    def ServerErrorHandler(self, *args):
        print '\n **** ERROR REPORT **** '
        print 'Server threw us an error.  Args:', args
        ev = network.ServerErrorEvent()
        events.post(ev)
        print ' ^*** ERROR REPORT ***^ \n'


#------------------------------------------------------------------------------
class PhonyEventModule(object):
    Event = events.Event
    #--------------------------------------------------------------------------
    def post(self, arg1, *extraArgs, **kwargs):
        pass

    #--------------------------------------------------------------------------
    def registerListener(self, listener):
        pass

    #--------------------------------------------------------------------------
    def unregisterListener(self, listener):
        pass

#------------------------------------------------------------------------------
class PhonyModel:
    '''This isn't the authouritative model.  That one exists on the
    server.  This is a model to store local state and to interact with
    the local EventManager.
    '''

    #--------------------------------------------------------------------------
    def __init__(self, evModule, sharedObjectRegistry):
        self.sharedObjs = sharedObjectRegistry
        self.game = None
        self.server = None
        self.phonyEvModule = PhonyEventModule()
        self.realEvModule = evModule
        self.neededObjects = []

        self.realEvModule.registerListener( self )

    #----------------------------------------------------------------------
    def GameSyncReturned(self, response):
        gameID, gameDict = response
        print "GameSyncReturned : ", gameID, gameDict
        self.sharedObjs[gameID] = self.game
        # StateReturned returns a deferred, pass it on to keep the
        # chain going.
        return self.StateReturned( response )

    #----------------------------------------------------------------------
    def StateReturned(self, response):
        """this is a callback that is called in response to
        invoking GetObjectState on the server"""

        print "looking for ", response
        objID, objDict = response
        if objID == 0:
            print "GOT ZERO -- TODO: better error handler here"
            return None
        obj = self.sharedObjs[objID]

        print 'setting copyable state on', obj
        neededObjIDs = obj.setCopyableState(objDict, self.sharedObjs)
        if not neededObjIDs:
            #we successfully set the state and no further objects
            #are needed to complete the current object
            if objID in self.neededObjects:
                self.neededObjects.remove(objID)

        else:
            #to complete the current object, we need to grab the
            #state from some more objects on the server.  The IDs
            #for those needed objects were passed back 
            #in neededObjIDs
            for neededObjID in neededObjIDs:
                if neededObjID not in self.neededObjects:
                    self.neededObjects.append(neededObjID)
            print "failed.  still need ", self.neededObjects


        retval = self.GetAllNeededObjects()
        if retval:
            # retval is a Deferred - returning it causes a chain
            # to be formed.  The original deferred must wait for
            # this new one to return before it calls its next
            # callback
            return retval

    #----------------------------------------------------------------------
    def GetAllNeededObjects(self):
        if len(self.neededObjects) == 0:
            # this is the recursion-ending condition.  If there are
            # no more objects needed to be grabbed from the server
            # then we can try to setCopyableState on them again and
            # we should now have all the needed objects, ensuring
            # that setCopyableState succeeds
            return

        # still in the recursion step.  Try to get the object state for
        # the objectID on the top of the stack.  Note that the 
        # recursion is done via a deferred, which may be confusing
        nextID = self.neededObjects[-1]
        print "next one to grab: ", nextID
        remoteResponse = self.server.callRemote("GetObjectState",nextID)
        remoteResponse.addCallback(self.StateReturned)
        remoteResponse.addErrback(self.ServerErrorHandler, 'allNeededObjs')
        return remoteResponse

    #----------------------------------------------------------------------
    def notify(self, event):
        if event.name == 'ServerConnectEvent':
            self.server = event.args[0]
            #when we connect to the server, we should get the
            #entire game state.  this also applies to RE-connecting
            if not self.game:
                catan.init(self.phonyEvModule)
                self.game = catan.game
                gameID = id(self.game)
                self.sharedObjs[gameID] = self.game
            remoteResponse = self.server.callRemote("GetGameSync")
            remoteResponse.addCallback(self.GameSyncReturned)
            remoteResponse.addCallback(self.GameSyncCallback, gameID)
            remoteResponse.addErrback(self.ServerErrorHandler, 'ServerConnect')

        elif isinstance( event, network.CopyableStageChange ):
            #self.game.setStage(event.newStage)
            ev = catan.StageChange(event.newStage)
            self.realEvModule.post(ev)

        elif isinstance( event, network.ServerErrorEvent ):
            from pprint import pprint
            print 'Client state at the time of server error:'
            pprint(self.sharedObjs)

        elif isinstance( event, network.CopyablePlayerJoin ):
            print 'copyable player join event'
            playerID = event.playerID
            if not self.sharedObjs.has_key(playerID):
                player = network.Placeholder(playerID, self.sharedObjs)
            remoteResponse = self.server.callRemote("GetObjectState", playerID)
            remoteResponse.addCallback(self.StateReturned)
            remoteResponse.addCallback(self.PlayerJoinCallback, playerID)
            remoteResponse.addErrback(self.ServerErrorHandler, 'PlayerJoin')

        #if isinstance( event, network.CopyableMapBuiltEvent ):
        #    mapID = event.mapID
        #    if not self.sharedObjs.has_key(mapID):
        #        self.sharedObjs[mapID] = self.game.map
        #    remoteResponse = self.server.callRemote("GetObjectState", mapID)
        #    remoteResponse.addCallback(self.StateReturned)
        #    remoteResponse.addCallback(self.MapBuiltCallback, mapID)
        #    remoteResponse.addErrback(self.ServerErrorHandler, 'MapBuilt')

        #if isinstance( event, network.CopyableCharactorPlaceEvent ):
        #    charactorID = event.charactorID
        #    if not self.sharedObjs.has_key(charactorID):
        #        charactor = self.game.players[0].charactors[0]
        #        self.sharedObjs[charactorID] = charactor
        #    remoteResponse = self.server.callRemote("GetObjectState", charactorID)
        #    remoteResponse.addCallback(self.StateReturned)
        #    remoteResponse.addCallback(self.CharactorPlaceCallback, charactorID)
        #    remoteResponse.addErrback(self.ServerErrorHandler, 'CharPlace')

        #if isinstance( event, network.CopyableCharactorMoveEvent ):
        #    charactorID = event.charactorID
        #    if not self.sharedObjs.has_key(charactorID):
        #        charactor = self.game.players[0].charactors[0]
        #        self.sharedObjs[charactorID] = charactor
        #    remoteResponse = self.server.callRemote("GetObjectState", charactorID)
        #    remoteResponse.addCallback(self.StateReturned)
        #    remoteResponse.addCallback(self.CharactorMoveCallback, charactorID)
        #    remoteResponse.addErrback(self.ServerErrorHandler, 'CharMove')

    #----------------------------------------------------------------------
    def GameSyncCallback(self, deferredResult, gameID):
        print 'got game sync callback.  args', gameID
        self.realEvModule.post('RefreshState')
        global pygameView
        if not pygameView:
            pygameView = pygameview.PygameView()
    #----------------------------------------------------------------------
    def PlayerJoinCallback(self, deferredResult, playerID):
        player = self.sharedObjs[playerID]
        self.realEvModule.post('PlayerJoin', player)
    #----------------------------------------------------------------------
    def ServerErrorHandler(self, failure, *args):
        print '\n **** ERROR REPORT **** '
        print 'Server threw PhonyModel an error.  failure:', failure
        print 'failure traceback:', failure.getTraceback()
        print 'Server threw PhonyModel an error.  Args:', args
        ev = network.ServerErrorEvent()
        self.realEvModule.post(ev)
        print ' ^*** ERROR REPORT ***^ \n'


#class DebugDict(dict):
    #def __setitem__(self, *args):
        #print ''
        #print '        set item', args
        #return dict.__setitem__(self, *args)

pygameView = None
phonyModel = None # For debugging
serverView = None # For debugging
#------------------------------------------------------------------------------
def main():
    global avatarID
    if len(sys.argv) > 1:
        avatarID = sys.argv[1]
    else:
        print 'You should provide a username on the command line'
        print 'Defaulting to username "user1"'
        time.sleep(1)
        avatarID = 'user1'
        
    sharedObjectRegistry = {}
    keybd = pygameview.KeyboardController( playerName=avatarID )
    spinner = pygameview.CPUSpinnerController()
    pygameview.pygame.init() # initialize Pygame so that the spinner can spin

    global phonyModel # For debugging
    phonyModel = PhonyModel( events, sharedObjectRegistry  )

    global serverView # For debugging
    serverView = NetworkServerView(sharedObjectRegistry)
    
    try:
        spinner.run()
    except Exception, ex:
        print 'got exception (%s)' % ex, 'killing reactor'
        import logging
        logging.basicConfig()
        logging.exception(ex)
        serverView.Disconnect()


if __name__ == "__main__":
    main()
