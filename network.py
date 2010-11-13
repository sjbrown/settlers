
import events
import catan
from catan import *
from mapmodel import Tile, Edge, Corner
from twisted.spread import pb

# A list of ALL possible events that a server can send to a client
serverToClientEvents = [
'BoardCreated',
'CardHarvestOver',
'ChooseTwoCards',
'ConfirmProposal',
'CountdownOver',
'DiceRoll',
'Discard',
'Error',
'EventNotAllowedAtThisStage',
'FatalEvent',
'Harvest',
'ItemPlaced',
'ItemRemoved',
'MaritimeTrade',
'Monopoly',
'MonopolyGive',
'PlayerCannotAfford',
'PlayerCannotBuy',
'PlayerDrewVictoryCard',
'PlayerJoin',
'PlayerPlacing',
'PlayerSet',
'ProposeTrade',
'RefreshState',
'Rob',
'RobberPlaced',
'StageChange',
]
# A list of ALL possible events that a client can send to a server
clientToServerEvents = [
'BuyRequest'
'ChooseTwoCardsRequest'
'ConfirmProposalRequest'
'DiceRollRequest'
'DiscardRequest'
'MaritimeTradeRequest'
'MonopolyRequest'
'PlayVictoryCardRequest'
'PlayerJoinRequest'
'ProposeTrade'
'RefreshState'
'RobRequest'
'RobberPlaceRequest'
'SkipRobRequest'
'TurnFinishRequest'
]

#------------------------------------------------------------------------------
#Mix-In Helper Functions
#------------------------------------------------------------------------------
def MixInClass( origClass, addClass ):
    if addClass not in origClass.__bases__:
        origClass.__bases__ += (addClass,)

#------------------------------------------------------------------------------
def MixInCopyClasses( someClass ):
    MixInClass( someClass, pb.Copyable )
    MixInClass( someClass, pb.RemoteCopy )

#------------------------------------------------------------------------------
class Placeholder(object):
    def __init__(self, objID, reg):
        if objID in reg:
            raise Exception('Making a placeholder for an obj that has'
                            ' already been retrieved (%s)' % objID)
        self.placeholder_id = objID
        reg[objID] = self
    def placeholder_setDict(self, myDict):
        self.placeholder_dict = myDict
    def placeholder_setClass(self, cls, reg):
        self.__class__ = cls
        neededObjIDs = self.setCopyableState(self.placeholder_dict, reg)
        return neededObjIDs
        # just ignore the neededObjIDs as the load() function will fill
        # everything in.... hopefully
    def setCopyableState(self, objDict, reg):
        print 'in placeholder setcopyablestate'
        self.placeholder_setDict(objDict)
        clsPath, clsName = objDict['__classpathAndName']
        try:
            # TODO: big potential security hole here. FIXME
            module = __import__(clsPath, globals(), locals())
            cls = getattr(module, clsName)
        except Exception, ex:
            raise
        return self.placeholder_setClass(cls, reg)



#------------------------------------------------------------------------------
def serialize(obj, registry, reverseRegistry=None):
    '''Serialize any obj.
    Python literals are returned as is.
    Sequences and Dicts need to serialize the objects they contain.
    Any other type of object needs to be turned into an ID number (integer).
    If reverseRegistry is provided, and reverseRegistry[obj] exists, the ID
    number will be that value.  This is useful in the case of clients, where
    the authoritative ID number came from the server.  Otherwise, the ID
    number will simply be id(obj)
    '''
    objType = type(obj)
    if objType in [str, unicode, int, float, bool, type(None)]:
        return obj

    elif objType in [list, tuple]:
        new_obj = []
        for sub_obj in obj:
            new_obj.append(serialize(sub_obj, registry))
        return new_obj

    elif objType == dict:
        new_obj = {}
        for key, val in obj.items():
            new_obj[serialize(key, registry)] = serialize(val, registry)
        return new_obj

    else:
        if reverseRegistry and reverseRegistry[obj]:
            objID = reverseRegistry[obj]
        else:
            objID = id(obj)
        registry[objID] = obj
        return objID
        
#------------------------------------------------------------------------------
class Serializable:
    '''The Serializable interface.
    All objects inheriting Serializable must have a .copyworthy_attrs member.

    They can also optionally have a .registry_attrs member, which tells the
    unserializing function which attributes are "complex" objects - objects
    which should be found in the registry

    Also, if an attribute needs to be unserialized in a custom way,
    Serializable objects can implement functions named "unserialize_ATTR",
    where ATTR is the name of the attribute.  This function will be called
    and be expected to populate the attribute and return a list of any further
    needed object IDs.
    '''
    registry_attrs = [] # overriden by subclasses (implementors)

    def preUnserialize(self):
        pass # overriden by subclasses (implementors)
    def postUnserialize(self):
        pass # overriden by subclasses (implementors)

    def getStateToCopy(self, registry):
        d = {}
        cls = self.__class__
        d['__classpathAndName'] = cls.__module__, cls.__name__
        for attr in self.copyworthy_attrs:
            val = getattr(self, attr)
            new_val = serialize(val, registry)
            d[attr] = new_val

        return d

    def setCopyableState(self, stateDict, registry):
        self.preUnserialize()
        neededObjIDs = []

        for attrName, value in stateDict.items():
            if hasattr(self, 'unserialize_'+attrName):
                method = getattr(self, 'unserialize_'+attrName)
                neededObjIDs_ = method(stateDict, registry)
                neededObjIDs += neededObjIDs_
            elif attrName in self.registry_attrs:
                neededObjIDs_ = self.genericUnserialize(stateDict,
                                                   registry, attrName, value)
                neededObjIDs += neededObjIDs_
            else:
                setattr(self, attrName, value)

        self.postUnserialize()
        print self.__class__, 'object still needs', neededObjIDs
        return neededObjIDs

    def genericUnserialize(self, stateDict, registry, attrName, value):
        neededObjIDs = []

        if value == None:
            setattr(self, attrName, value)
        elif value in registry:
            setattr(self, attrName, registry[value])
        else:
            placeholder = Placeholder(value, registry)
            setattr(self, attrName, registry[value])
            neededObjIDs.append(value)

        return neededObjIDs


def unserialize_shallow_list(attrName):
    def unserialize_fn(self, stateDict, registry):
        neededObjIDs = []
        newList = []
        setattr(self, attrName,  newList)
        itemIDs = stateDict[attrName]
        for value in itemIDs:
            if value in registry:
                newList.append(registry[value])
            else:
                placeholder = Placeholder(value, registry)
                newList.append(registry[value])
                neededObjIDs.append(value)
        return neededObjIDs
    return unserialize_fn
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
# For each event class, if it is sendable over the network, we have 
# to Mix In the "copy classes", or make a replacement event class that is 
# copyable

##------------------------------------------------------------------------------
## QuitEvent
## Direction: Client to Server only
#MixInCopyClasses( QuitEvent )
#pb.setUnjellyableForClass(QuitEvent, QuitEvent)
#clientToServerEvents.append( QuitEvent )
#
##------------------------------------------------------------------------------
## GameStartRequest
## Direction: Client to Server only
#MixInCopyClasses( GameStartRequest )
#pb.setUnjellyableForClass(GameStartRequest, GameStartRequest)
#clientToServerEvents.append( GameStartRequest )


#------------------------------------------------------------------------------
class ServerErrorEvent(events.Event):
    def __init__(self):
        self.name = "Server Err Event"

#------------------------------------------------------------------------------
class ClientErrorEvent(events.Event):
    def __init__(self):
        self.name = "Client Err Event"

#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# PlayerJoinRequest
# Direction: Client to Server only
class CopyablePlayerJoinRequest(events.Event, pb.Copyable, pb.RemoteCopy):
    def __init__(self, event, registry):
        self.name = event.name
        self.playerName = event.args[0]
pb.setUnjellyableForClass(CopyablePlayerJoinRequest, CopyablePlayerJoinRequest)
clientToServerEvents.append(CopyablePlayerJoinRequest)

#------------------------------------------------------------------------------
# FillWithCPUPlayersRequest
# Direction: Client to Server only
class CopyableFillWithCPUPlayersRequest(events.Event, pb.Copyable, pb.RemoteCopy):
    def __init__(self, event, registry):
        self.name = event.name
pb.setUnjellyableForClass(CopyableFillWithCPUPlayersRequest,
                          CopyableFillWithCPUPlayersRequest)
clientToServerEvents.append(CopyableFillWithCPUPlayersRequest)

#------------------------------------------------------------------------------
# PlayerJoin
# Direction: Server to Client only
class CopyablePlayerJoinEvent(events.Event, pb.Copyable, pb.RemoteCopy):
    def __init__(self, event, registry):
        self.name = "Copyable" + event.name
        self.playerID = id(event.args[0])
        registry[self.playerID] = event.args[0]
pb.setUnjellyableForClass(CopyablePlayerJoinEvent, CopyablePlayerJoinEvent)
serverToClientEvents.append(CopyablePlayerJoinEvent)

#------------------------------------------------------------------------------
# StageChange
# Direction: Server to Client only
class CopyableStageChange(pb.Copyable, pb.RemoteCopy):
    def __init__(self, event, registry):
        self.name = "Copyable" + event.name
        self.newStage = event.newStage
pb.setUnjellyableForClass(CopyableStageChange, CopyableStageChange)
serverToClientEvents.append( CopyableStageChange )

##------------------------------------------------------------------------------
## MapBuiltEvent
## Direction: Server to Client only
#class CopyableMapBuiltEvent( pb.Copyable, pb.RemoteCopy):
#    def __init__(self, event, registry ):
#        self.name = "Copyable Map Finished Building Event"
#        self.mapID = id( event.map )
#        registry[self.mapID] = event.map
#
#pb.setUnjellyableForClass(CopyableMapBuiltEvent, CopyableMapBuiltEvent)
#serverToClientEvents.append( CopyableMapBuiltEvent )
#
##------------------------------------------------------------------------------
## ItemPlaceEvent
## Direction: Server to Client only
#class CopyableItemPlaceEvent( pb.Copyable, pb.RemoteCopy):
#    def __init__(self, event, registry ):
#        self.name = "Copyable " + event.name
#        self.ItemID = id( event.item )
#        registry[self.itemID] = event.item
#
#pb.setUnjellyableForClass(CopyableItemPlaceEvent, CopyableItemPlaceEvent)
#serverToClientEvents.append( CopyableItemPlaceEvent )

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
# For any objects that we need to send in our events, we have to give them
# getStateToCopy() and setCopyableState() methods so that we can send a 
# network-friendly representation of them over the network.

#------------------------------------------------------------------------------
class CopyableGame(Serializable):
    copyworthy_attrs = ['state', 'players', 'board']
    registry_attrs = ['state', 'board']

    def preUnserialize(self):
        print 'CopyableGame is pre unserialize'

    def postUnserialize(self):
        self.dice = Dice()
        self._longestRoadPlayer = None
        self._longestRoadLength = 0
        self._largestArmyPlayer = None
        self._largestArmySize = 0
        events.registerListener(self)

    def unserialize_players(self, stateDict, registry):
        neededObjIDs = []
        self.players = []
        playerIDs = stateDict['players']
        for value in playerIDs:
            if value in registry:
                self.players.append(registry[value])
            else:
                placeholder = Placeholder(value, registry)
                self.players.append(placeholder)
                neededObjIDs.append(value)
        return neededObjIDs
            
MixInClass( Game, CopyableGame )

#------------------------------------------------------------------------------
class CopyableGameState(Serializable):
    copyworthy_attrs = ['game', '_stage', '_activePlayer',
                        'initialPlacementDirection', 'awaitingDiscard']
    registry_attrs = ['game', '_activePlayer']

    def getStateToCopy(self, registry):
        return Serializable.getStateToCopy(self, registry)

    def unserialize_awaitingDiscard(self, stateDict, registry):
        neededObjIDs = []
        self.awaitingDiscard = []
        playerIDs = stateDict['awaitingDiscard']
        for value in playerIDs:
            if value in registry:
                self.awaitingDiscard.append(registry[value])
            else:
                placeholder = Placeholder(value, registry)
                self.awaitingDiscard.append(placeholder)
                neededObjIDs.append(value)
        return neededObjIDs

    def preUnserialize(self):
        print 'CopyableGameState is pre unserialize'
    def postUnserialize(self):
        events.registerListener(self)

MixInClass( GameState, CopyableGameState )

#------------------------------------------------------------------------------
class CopyableRobber(Serializable):
    copyworthy_attrs = ['_tile']
    registry_attrs = ['_tile']

    def postUnserialize(self):
        events.registerListener(self)

MixInClass( Robber, CopyableRobber )

#------------------------------------------------------------------------------
class CopyableRoad(Serializable):
    copyworthy_attrs = ['owner', 'location']
    registry_attrs = ['owner', 'location']

MixInClass( Road, CopyableRoad )

#------------------------------------------------------------------------------
class CopyableSettlement(Serializable):
    copyworthy_attrs = ['owner', 'location']
    registry_attrs = ['owner', 'location']

MixInClass( Settlement, CopyableSettlement )

#------------------------------------------------------------------------------
class CopyableCity(CopyableSettlement): pass

MixInClass( City, CopyableCity )

#------------------------------------------------------------------------------
class CopyableCard(Serializable):
    def getStateToCopy(self, registry):
        return dict(cls=self.__class__.__name__)

    def setCopyableState(self, stateDict, registry):
        import catan
        cls = getattr(catan, stateDict['cls'])
        self.__class__ = cls
        return []

MixInClass( Card, CopyableCard )

#------------------------------------------------------------------------------
class CopyableVictoryCard(CopyableCard): pass
MixInClass( VictoryCard, CopyableVictoryCard )

#------------------------------------------------------------------------------
class CopyableTerrain(Serializable):
    def getStateToCopy(self, registry):
        return dict(cls=self.__class__.__name__)

    def setCopyableState(self, stateDict, registry):
        import catan
        cls = getattr(catan, stateDict['cls'])
        self.__class__ = cls
        return []

MixInClass( Terrain, CopyableTerrain )

#------------------------------------------------------------------------------
class CopyablePip(Serializable):
    copyworthy_attrs = ['value']

MixInClass( Pip, CopyablePip )

#------------------------------------------------------------------------------
class CopyableBoard(Serializable):
    copyworthy_attrs = ['robber']
    registry_attrs = ['robber']

    def getStateToCopy(self, registry):
        d = Serializable.getStateToCopy(self, registry)

        d.update({
        'centerTile': mapmodel.centerTile.name,
        'allTiles':   [(id(t), t.getStateToCopy(registry))
                       for t in mapmodel.allTiles],
        'allCorners': [(id(c), c.getStateToCopy(registry))
                       for c in mapmodel.allCorners],
        'allEdges':   [(id(e), e.getStateToCopy(registry))
                       for e in mapmodel.allEdges],
        })
        d['cornersToTiles'] = {}
        for c, tlist in mapmodel.cornersToTiles.items():
            d['cornersToTiles'][id(c)] = [id(t) for t in tlist]
        d['edgesToTiles'] = {}
        for e, tlist in mapmodel.edgesToTiles.items():
            d['edgesToTiles'][id(e)] = [id(t)for t in tlist]
        d['ports'] = []
        for p in self.ports:
            p2 = list(p)
            if p[0] != None:
                p2[0] = p[0].__name__
            d['ports'].append(p2)
        return d

    def setCopyableState(self, stateDict, registry):
        neededObjIDs = []
        self.tiles = []
        for tID, tdict in stateDict['allTiles']:
            t = mapmodel.Tile()
            self.tiles.append(t)
            registry[tID] = t

        for cID, cdict in stateDict['allCorners']:
            c = mapmodel.Corner()
            registry[cID] = c

        for eID, edict in stateDict['allEdges']:
            e = mapmodel.Edge()
            registry[eID] = e

        for tID, tdict in stateDict['allTiles']:
            t = registry[tID]
            neededObjIDs += t.setCopyableState(tdict, registry)
            if stateDict['centerTile'] == t.name:
                mapmodel.centerTile = t

        for cID, cdict in stateDict['allCorners']:
            c = registry[cID]
            neededObjIDs += c.setCopyableState(cdict, registry)
            assert c.name == cdict['name']
            tileIDs = stateDict['cornersToTiles'][cID]
            for tID in tileIDs:
                tile = registry[tID]
                tile.corners.append(c)
                if c in mapmodel.cornersToTiles:
                    mapmodel.cornersToTiles[c].append(tile)
                else:
                    mapmodel.cornersToTiles[c] = [tile]

        for eID, edict in stateDict['allEdges']:
            e = registry[eID]
            neededObjIDs += e.setCopyableState(edict, registry)
            assert e.name == edict['name']
            cornerIDs = edict['corners']
            for cID in cornerIDs:
                corner = registry[cID]
                if e not in corner.edges:
                    corner.addEdge(e, recurse=False)
            tileIDs = stateDict['edgesToTiles'][eID]
            for tID in tileIDs:
                tile = registry[tID]
                e.addTile(tile, recurse=False)
                tile.addEdge(e)

        return neededObjIDs +\
               Serializable.setCopyableState(self, stateDict, registry)

    def unserialize_ports(self, stateDict, registry):
        neededObjIDs = []
        self.ports = []
        for cardClassName, num in stateDict['ports']:
            if cardClassName == None:
                cardClass = None
            else:
                cardClass = getattr(catan, cardClassName)
            port = catan.Port((cardClass, num))
            self.ports.append(port)
        return neededObjIDs

    def postUnserialize(self):
        self.populateGraphicalPositions()
        self.layOutPorts()
        events.registerListener(self)

MixInClass( Board, CopyableBoard )

#------------------------------------------------------------------------------
class CopyableTile(Serializable):
    # NOTE: corners and edges are done by the CopyableBoard
    copyworthy_attrs = ['pip', 'robber', 'terrain']
    registry_attrs = ['pip', 'robber', 'terrain']

MixInClass( Tile, CopyableTile )

#------------------------------------------------------------------------------
class CopyableCorner(Serializable):
    # NOTE: edges are done by the CopyableBoard
    copyworthy_attrs = ['stuff', 'cornerDistance', 'name']

    def unserialize_stuff(self, stateDict, registry):
        neededObjIDs = []
        self.stuff = []
        itemIDs = stateDict['stuff']
        for value in itemIDs:
            if value in registry:
                self.stuff.append(registry[value])
            else:
                placeholder = Placeholder(value, registry)
                self.stuff.append(registry[value])
                neededObjIDs.append(value)
        return neededObjIDs

MixInClass( Corner, CopyableCorner )

#------------------------------------------------------------------------------
class CopyableEdge(Serializable):
    # NOTE: tiles are done by the CopyableBoard
    copyworthy_attrs = ['stuff', 'name', 'corners']

    def unserialize_corners(self, stateDict, registry):
        neededObjIDs = []
        self.corners = []
        cornerIDs = stateDict['corners']
        for value in cornerIDs:
            if value in registry:
                self.corners.append(registry[value])
            else:
                placeholder = Placeholder(value, registry)
                self.corners.append(registry[value])
                neededObjIDs.append(value)
        return neededObjIDs

    def unserialize_stuff(self, stateDict, registry):
        neededObjIDs = []
        self.stuff = []
        itemIDs = stateDict['stuff']
        for value in itemIDs:
            if value in registry:
                self.stuff.append(registry[value])
            else:
                placeholder = Placeholder(value, registry)
                self.stuff.append(registry[value])
                neededObjIDs.append(value)
        return neededObjIDs

MixInClass( Edge, CopyableEdge )

#------------------------------------------------------------------------------
class CopyablePlayer(Serializable):
    copyworthy_attrs = ['identifier', 'color', 'latestItem', 'items', 'cards',
                        'victoryCards', 'playedVictoryCards',
                        'victoryCardPlayedThisTurn',
                        'victoryCardsBoughtThisTurn']

    unserialize_items = unserialize_shallow_list('items')
    unserialize_cards = unserialize_shallow_list('cards')
    unserialize_victoryCards = unserialize_shallow_list('victoryCards')
    unserialize_playedVictoryCards = \
     unserialize_shallow_list('playedVictoryCards')
    unserialize_victoryCardsBoughtThisTurn = \
     unserialize_shallow_list('victoryCardsBoughtThisTurn')

    def postUnserialize(self):
        self.activeItem = None
        self.offer = []
        self.wants = []
        events.registerListener(self)

MixInClass( Player, CopyablePlayer )


#------------------------------------------------------------------------------
def test_Game():
    players = catan.game.players
    reg1 = {id(players[0]): players[0],
            id(players[1]): players[1],
            id(players[2]): players[2],
            id(players[3]): players[3],
            id(catan.game.state): catan.game.state,
            id(catan.game.board): catan.game.board,
            }
    reg2 = {}
    stateDict = {'players': [id(players[0]), id(players[1]),
                             id(players[2]), id(players[3])],
                 'state': id(catan.game.state),
                 'board': id(catan.game.board)}
    retval = catan.game.getStateToCopy(reg2)
    assert retval == stateDict
    neededObjIDs = catan.game.setCopyableState(stateDict, reg1)
    print 'NEED', neededObjIDs
    print ''


def test_Player():
    players = catan.game.players
    p1 = players[0]
    stateDict= {
     'color': [50, 10, 215],
     'identifier': 1,
     'latestItem': id(p1.latestItem),
     'cards': [],
     'victoryCards': [],
     'playedVictoryCards': [],
     'items': [id(p1.items[0]), id(p1.items[1])],
    }
    reg1 = {id(p1.items[0]): p1.items[0],
            id(p1.items[1]): p1.items[1],
           }
    reg2 = {}

    retval = p1.getStateToCopy(reg2)
    assert retval == stateDict
    neededObjIDs = p1.setCopyableState(stateDict, reg1)
    print 'NEED', neededObjIDs
    print ''

    p4 = players[3]
    stateDict = {
      'color': [200, 10, 95],
      'identifier': 4,
      'latestItem': None,
      'cards': [],
      'victoryCards': [],
      'playedVictoryCards': [],
      'items': [id(p4.items[0])],
      }
    reg1.update( {id(p4.items[0]): p4.items[0],} )

    retval = p4.getStateToCopy(reg2)
    assert retval == stateDict
    neededObjIDs = p4.setCopyableState(stateDict, reg1)
    print 'NEED', neededObjIDs
    print ''

def test_Board():
    stateDict = {
     'robber': 17528848,
     'centerTile': 't01',
     'allTiles': [
          (17588560, {'pip': 17588496, 'robber': None, 'terrain': 17885968}),
          (17588752, {'pip': 17563600, 'robber': None, 'terrain': 17885712}),
          (17588880, {'pip': 17588304, 'robber': None, 'terrain': 17885776}),
          (17589136, {'pip': 17563536, 'robber': None, 'terrain': 17885648}),
          (17589392, {'pip': 17588368, 'robber': None, 'terrain': 17885840}),
          (17589648, {'pip': 17563472, 'robber': None, 'terrain': 17885456}),
          (17589904, {'pip': 17588432, 'robber': None, 'terrain': 17885904}),
          (17590288, {'pip': 17563088, 'robber': None, 'terrain': 17885072}),
          (17590544, {'pip': 17562960, 'robber': None, 'terrain': 17884944}),
          (17590800, {'pip': 17563024, 'robber': None, 'terrain': 17885008}),
          (17591184, {'pip': 17563216, 'robber': None, 'terrain': 17885200}),
          (17591440, {'pip': 17563152, 'robber': None, 'terrain': 17885136}),
          (17591824, {'pip': 17562832, 'robber': None, 'terrain': 17884816}),
          (17592080, {'pip': 17562768, 'robber': None, 'terrain': 17884880}),
          (17604816, {'pip': None, 'robber': 17528848, 'terrain': 17885328}),
          (17605072, {'pip': 17563280, 'robber': None, 'terrain': 17885264}),
          (17605456, {'pip': 17563408, 'robber': None, 'terrain': 17885520}),
          (17605712, {'pip': 17562896, 'robber': None, 'terrain': 17884752}),
          (17606096, {'pip': 17563344, 'robber': None, 'terrain': 17885584}),
          ],
     'allCorners': [
        (17588624, {'cornerDistance': 0, 'name': 'c01', 'stuff': [17886224]}),
        (17589008, {'cornerDistance': 0, 'name': 'c02', 'stuff': []}),
        (17589264, {'cornerDistance': 0, 'name': 'c03', 'stuff': []}),
        (17589520, {'cornerDistance': 0, 'name': 'c04', 'stuff': [17902480]}),
        (17589776, {'cornerDistance': 0, 'name': 'c05', 'stuff': [17903312]}),
        (17590032, {'cornerDistance': 0, 'name': 'c06', 'stuff': []}),
        (17590160, {'cornerDistance': 1, 'name': 'c07', 'stuff': []}),
        (17590416, {'cornerDistance': 1, 'name': 'c08', 'stuff': []}),
        (17590672, {'cornerDistance': 2, 'name': 'c09', 'stuff': []}),
        (17590928, {'cornerDistance': 2, 'name': 'c10', 'stuff': []}),
        (17591056, {'cornerDistance': 1, 'name': 'c11', 'stuff': []}),
        (17591312, {'cornerDistance': 2, 'name': 'c12', 'stuff': []}),
        (17591568, {'cornerDistance': 2, 'name': 'c13', 'stuff': []}),
        (17591696, {'cornerDistance': 1, 'name': 'c14', 'stuff': []}),
        (17591952, {'cornerDistance': 2, 'name': 'c15', 'stuff': []}),
        (17592208, {'cornerDistance': 2, 'name': 'c16', 'stuff': []}),
        (17604688, {'cornerDistance': 1, 'name': 'c17', 'stuff': []}),
        (17604944, {'cornerDistance': 2, 'name': 'c18', 'stuff': []}),
        (17605200, {'cornerDistance': 2, 'name': 'c19', 'stuff': []}),
        (17605328, {'cornerDistance': 1, 'name': 'c20', 'stuff': []}),
        (17605584, {'cornerDistance': 2, 'name': 'c21', 'stuff': []}),
        (17605840, {'cornerDistance': 2, 'name': 'c22', 'stuff': []}),
        (17605968, {'cornerDistance': 2, 'name': 'c23', 'stuff': []}),
        (17606224, {'cornerDistance': 2, 'name': 'c24', 'stuff': []}),
        (17606352, {'cornerDistance': 3, 'name': 'c25', 'stuff': []}),
        (17606544, {'cornerDistance': 3, 'name': 'c26', 'stuff': []}),
        (17606736, {'cornerDistance': 4, 'name': 'c27', 'stuff': []}),
        (17606800, {'cornerDistance': 3, 'name': 'c28', 'stuff': []}),
        (17606992, {'cornerDistance': 3, 'name': 'c29', 'stuff': []}),
        (17607184, {'cornerDistance': 4, 'name': 'c30', 'stuff': []}),
        (17607248, {'cornerDistance': 4, 'name': 'c31', 'stuff': []}),
        (17607376, {'cornerDistance': 4, 'name': 'c32', 'stuff': []}),
        (17607440, {'cornerDistance': 3, 'name': 'c33', 'stuff': []}),
        (17607632, {'cornerDistance': 3, 'name': 'c34', 'stuff': []}),
        (17607824, {'cornerDistance': 4, 'name': 'c35', 'stuff': []}),
        (17607888, {'cornerDistance': 4, 'name': 'c36', 'stuff': []}),
        (17608016, {'cornerDistance': 4, 'name': 'c37', 'stuff': []}),
        (17608080, {'cornerDistance': 3, 'name': 'c38', 'stuff': []}),
        (17608272, {'cornerDistance': 3, 'name': 'c39', 'stuff': []}),
        (17608464, {'cornerDistance': 4, 'name': 'c40', 'stuff': []}),
        (17608528, {'cornerDistance': 4, 'name': 'c41', 'stuff': []}),
        (17608656, {'cornerDistance': 4, 'name': 'c42', 'stuff': []}),
        (17883216, {'cornerDistance': 3, 'name': 'c43', 'stuff': []}),
        (17883408, {'cornerDistance': 3, 'name': 'c44', 'stuff': []}),
        (17883600, {'cornerDistance': 4, 'name': 'c45', 'stuff': []}),
        (17883664, {'cornerDistance': 4, 'name': 'c46', 'stuff': []}),
        (17883792, {'cornerDistance': 4, 'name': 'c47', 'stuff': []}),
        (17883856, {'cornerDistance': 3, 'name': 'c48', 'stuff': []}),
        (17884048, {'cornerDistance': 3, 'name': 'c49', 'stuff': []}),
        (17884240, {'cornerDistance': 4, 'name': 'c50', 'stuff': []}),
        (17884304, {'cornerDistance': 4, 'name': 'c51', 'stuff': []}),
        (17884432, {'cornerDistance': 4, 'name': 'c52', 'stuff': []}),
        (17884496, {'cornerDistance': 4, 'name': 'c53', 'stuff': []}),
        (17884624, {'cornerDistance': 4, 'name': 'c54', 'stuff': []})
        ],
        'allEdges': [
              (17588688, {'name': 'e01', 'stuff': [17902160]}),
              (17588816, {'name': 'e02', 'stuff': []}),
              (17588944, {'name': 'e03', 'stuff': []}),
              (17589072, {'name': 'e04', 'stuff': [17902608]}),
              (17589200, {'name': 'e05', 'stuff': []}),
              (17589328, {'name': 'e06', 'stuff': [17903568]}),
              (17589456, {'name': 'e07', 'stuff': []}),
              (17589584, {'name': 'e08', 'stuff': []}),
              (17589712, {'name': 'e09', 'stuff': []}),
              (17589840, {'name': 'e10', 'stuff': []}),
              (17589968, {'name': 'e11', 'stuff': []}),
              (17590096, {'name': 'e12', 'stuff': []}),
              (17590224, {'name': 'e13', 'stuff': []}),
              (17590352, {'name': 'e14', 'stuff': []}),
              (17590480, {'name': 'e15', 'stuff': []}),
              (17590608, {'name': 'e16', 'stuff': []}),
              (17590736, {'name': 'e17', 'stuff': []}),
              (17590864, {'name': 'e18', 'stuff': []}),
              (17590992, {'name': 'e19', 'stuff': []}),
              (17591120, {'name': 'e20', 'stuff': []}),
              (17591248, {'name': 'e21', 'stuff': []}),
              (17591376, {'name': 'e22', 'stuff': []}),
              (17591504, {'name': 'e23', 'stuff': []}),
              (17591632, {'name': 'e24', 'stuff': []}),
              (17591760, {'name': 'e25', 'stuff': []}),
              (17591888, {'name': 'e26', 'stuff': []}),
              (17592016, {'name': 'e27', 'stuff': []}),
              (17592144, {'name': 'e28', 'stuff': []}),
              (17592272, {'name': 'e29', 'stuff': []}),
              (17604752, {'name': 'e30', 'stuff': []}),
              (17604880, {'name': 'e31', 'stuff': []}),
              (17605008, {'name': 'e32', 'stuff': []}),
              (17605136, {'name': 'e33', 'stuff': []}),
              (17605264, {'name': 'e34', 'stuff': []}),
              (17605392, {'name': 'e35', 'stuff': []}),
              (17605520, {'name': 'e36', 'stuff': []}),
              (17605648, {'name': 'e37', 'stuff': []}),
              (17605776, {'name': 'e38', 'stuff': []}),
              (17605904, {'name': 'e39', 'stuff': []}),
              (17606032, {'name': 'e40', 'stuff': []}),
              (17606160, {'name': 'e41', 'stuff': []}),
              (17606288, {'name': 'e42', 'stuff': []}),
              (17606416, {'name': 'e43', 'stuff': []}),
              (17606480, {'name': 'e44', 'stuff': []}),
              (17606608, {'name': 'e45', 'stuff': []}),
              (17606672, {'name': 'e46', 'stuff': []}),
              (17606864, {'name': 'e47', 'stuff': []}),
              (17606928, {'name': 'e48', 'stuff': []}),
              (17607056, {'name': 'e49', 'stuff': []}),
              (17607120, {'name': 'e50', 'stuff': []}),
              (17607312, {'name': 'e51', 'stuff': []}),
              (17607504, {'name': 'e52', 'stuff': []}),
              (17607568, {'name': 'e53', 'stuff': []}),
              (17607696, {'name': 'e54', 'stuff': []}),
              (17607760, {'name': 'e55', 'stuff': []}),
              (17607952, {'name': 'e56', 'stuff': []}),
              (17608144, {'name': 'e57', 'stuff': []}),
              (17608208, {'name': 'e58', 'stuff': []}),
              (17608336, {'name': 'e59', 'stuff': []}),
              (17608400, {'name': 'e60', 'stuff': []}),
              (17608592, {'name': 'e61', 'stuff': []}),
              (17883280, {'name': 'e62', 'stuff': []}),
              (17883344, {'name': 'e63', 'stuff': []}),
              (17883472, {'name': 'e64', 'stuff': []}),
              (17883536, {'name': 'e65', 'stuff': []}),
              (17883728, {'name': 'e66', 'stuff': []}),
              (17883920, {'name': 'e67', 'stuff': []}),
              (17883984, {'name': 'e68', 'stuff': []}),
              (17884112, {'name': 'e69', 'stuff': []}),
              (17884176, {'name': 'e70', 'stuff': []}),
              (17884368, {'name': 'e71', 'stuff': []}),
              (17884560, {'name': 'e72', 'stuff': []})
              ],
       'cornersToTiles': {
                    17588624: [17588560, 17588752, 17588880],
                    17589008: [17588560, 17588752, 17589136],
                    17589264: [17588560, 17588880, 17589392],
                    17589520: [17588560, 17589136, 17589648],
                    17589776: [17588560, 17589392, 17589904],
                    17590032: [17588560, 17589648, 17589904],
                    17590160: [17588752, 17588880, 17590288],
                    17590416: [17588752, 17589136, 17590544],
                    17590672: [17588752, 17590288, 17590800],
                    17590928: [17588752, 17590544, 17590800],
                    17591056: [17588880, 17589392, 17591184],
                    17591312: [17588880, 17590288, 17591440],
                    17591568: [17588880, 17591184, 17591440],
                    17591696: [17589136, 17589648, 17591824],
                    17591952: [17589136, 17590544, 17592080],
                    17592208: [17589136, 17591824, 17592080],
                    17604688: [17589392, 17589904, 17604816],
                    17604944: [17589392, 17591184, 17605072],
                    17605200: [17589392, 17604816, 17605072],
                    17605328: [17589648, 17589904, 17605456],
                    17605584: [17589648, 17591824, 17605712],
                    17605840: [17589648, 17605456, 17605712],
                    17605968: [17589904, 17604816, 17606096],
                    17606224: [17589904, 17605456, 17606096],
                    17606352: [17590288, 17590800],
                    17606544: [17590288, 17591440],
                    17606800: [17590544, 17590800],
                    17606992: [17590544, 17592080],
                    17607440: [17591184, 17591440],
                    17607632: [17591184, 17605072],
                    17608080: [17591824, 17592080],
                    17608272: [17591824, 17605712],
                    17883216: [17604816, 17605072],
                    17883408: [17604816, 17606096],
                    17883856: [17605456, 17605712],
                    17884048: [17605456, 17606096],
                    17606736: [17590288],
                    17607184: [17590544],
                    17607248: [17590800],
                    17607376: [17590800],
                    17607824: [17591184],
                    17607888: [17591440],
                    17608016: [17591440],
                    17608464: [17591824],
                    17608528: [17592080],
                    17608656: [17592080],
                    17883600: [17604816],
                    17883664: [17605072],
                    17883792: [17605072],
                    17884240: [17605456],
                    17884304: [17605712],
                    17884432: [17605712],
                    17884496: [17606096],
                    17884624: [17606096]},
         'edgesToTiles': {
                  17588688: [17588560, 17588752],
                  17588816: [17588560, 17588880],
                  17589072: [17588560, 17589136],
                  17589328: [17588560, 17589392],
                  17589584: [17588560, 17589648],
                  17589840: [17588560, 17589904],
                  17590224: [17588752, 17590288],
                  17590480: [17588752, 17590544],
                  17590736: [17588752, 17590800],
                  17591120: [17588880, 17591184],
                  17591376: [17588880, 17591440],
                  17591760: [17589136, 17591824],
                  17592016: [17589136, 17592080],
                  17604752: [17589392, 17604816],
                  17605008: [17589392, 17605072],
                  17605392: [17589648, 17605456],
                  17605648: [17589648, 17605712],
                  17606032: [17589904, 17606096],
                  17606416: [17590288],
                  17606480: [17590800],
                  17606608: [17590288],
                  17606672: [17591440],
                  17606864: [17590544],
                  17606928: [17590800],
                  17607056: [17590544],
                  17607120: [17592080],
                  17607312: [17590800],
                  17607504: [17591184],
                  17607568: [17591440],
                  17607696: [17591184],
                  17607760: [17605072],
                  17607952: [17591440],
                  17608144: [17591824],
                  17608208: [17592080],
                  17608336: [17591824],
                  17608400: [17605712],
                  17608592: [17592080],
                  17883280: [17604816],
                  17883344: [17605072],
                  17883472: [17604816],
                  17883536: [17606096],
                  17883728: [17605072],
                  17883920: [17605456],
                  17883984: [17605712],
                  17884112: [17605456],
                  17884176: [17606096],
                  17884368: [17605712],
                  17884560: [17606096]
          },
    }
    reg1 = {}
    reg2 = {}

    retval = catan.game.board.getStateToCopy(reg2)
    assert stateDict.keys() == retval.keys()
       

if __name__ == '__main__':
    print 'Running tests...'
    import catan
    import events
    catan.init()
    events.post('PlayerJoin', catan.CPUPlayer(1))
    events.post('PlayerJoin', catan.CPUPlayer(2))
    events.post('PlayerJoin', catan.CPUPlayer(3))
    events.post('PlayerJoin', catan.HumanPlayer(4))
    events.post(events.Tick())

    test_Game()
    test_Player()
    test_Board()

