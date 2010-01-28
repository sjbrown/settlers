#! /usr/bin/env python

import time
import shlex
import random

import events
import mapmodel
from mapmodel import Tile

class Countdown(object):
    def __init__(self, seconds):
        self.startTime = time.time()
        self.seconds = seconds

    def pump(self):
        if time.time() > self.startTime + self.seconds:
            events.post('CountdownOver')


class StageChange(events.Event):
    def __init__(self, newStage):
        events.Event.__init__(self)
        self.newStage = newStage
    def __repr__(self):
        return '<StageChange Event %s>' % self.newStage
    __str__ = __repr__

class Stages:
    (
    waitingForPlayers,
    setup,
    initialPlacement,
    preRollRobber,
    roll,
    sevenRolledDiscard,
    rolledRobberPlacement,
    cardHarvest,
    playerTurn,
    gameOver,
    ) = [x[:-1] for x in shlex.split('''
    waitingForPlayers,
    setup,
    initialPlacement,
    preRollRobber,
    roll,
    sevenRolledDiscard,
    rolledRobberPlacement,
    cardHarvest,
    playerTurn,
    gameOver,
    ''')]
    
class TurnOptions:
    (
    playRobber,
    build,
    playYearOfPlenty,
    playMonopoly,
    trade,
    #) = range(5)
    ) = [x[:-1] for x in shlex.split('''
    playRobber,
    build,
    playYearOfPlenty,
    playMonopoly,
    trade,
    ''')]


class EventNotAllowedAtThisStage(Exception): pass

def allowedDuring(*allowedStages):
    def decoratr(fn):
        def wrappedfn(self, *args):
            print 'called ', fn
            print 'stage was', self.stage
            print 'supposed to be in', allowedStages
            if self.stage not in allowedStages:
                raise EventNotAllowedAtThisStage(fn.__name__, self.stage, allowedStages)
            print 'start with', args
            retval = fn(self, *args)
            print 'stop'
            return retval
        wrappedfn.__name__ = fn.__name__
        return wrappedfn
    return decoratr
        

class GameState(object):
    def __init__(self):
        self.board = None
        self.players = []
        self._stage = Stages.waitingForPlayers
        self._activePlayer = None
        self._activeCountdown = None
        self.initialPlacementDirection = 1
        events.registerListener(self)

    def getActivePlayer(self):
        return self._activePlayer
    def setActivePlayer(self, player):
        self._activePlayer = player
        events.post('PlayerSet', player)
    activePlayer = property(getActivePlayer, setActivePlayer)

    def getStage(self):
        return self._stage
    def setStage(self, stage):
        self._stage = stage
        #events.post('StageChange', stage)
        events.post(StageChange(stage))
    stage = property(getStage, setStage)

    def nextPlayer(self):
        idx = self.players.index(self.activePlayer)
        if self.stage == Stages.initialPlacement:
            if idx == len(self.players)-1 and self.initialPlacementDirection == 1:
                self.initialPlacementDirection = -1
                return #keep the player the same
            if idx == 0 and self.initialPlacementDirection == -1:
                assert False, 'Should never get here'
            idx += self.initialPlacementDirection
        else:
            idx += 1
            idx %= len(self.players)
        self.activePlayer = self.players[idx]
        print 'NExT PLAYER', self.activePlayer

    @allowedDuring(Stages.waitingForPlayers)
    def onPlayerJoin(self, player):
        self.players.append(player)
        if len(self.players) == 4:
            self.stage = Stages.setup
            self.board = Board()

    def onCountdownOver(self):
        self._activeCountdown = None
        if self.stage == Stages.initialPlacement:
            position = self.activePlayer.activeItem.findBestPosition()
            self.activePlayer.activeItem.place(position)

        if self.stage == Stages.roll:
            # TODO ...force a roll
            pass

    @allowedDuring(Stages.setup)
    def onBoardCreated(self, board):
        self.activePlayer = self.players[0]
        self.activePlayer.add(Settlement())
        self.stage = Stages.initialPlacement
        self._activeCountdown = Countdown(60)

    @allowedDuring(Stages.initialPlacement, Stages.playerTurn)
    def onItemPlaced(self, item):
        if self.stage == Stages.initialPlacement:
            if ( isinstance(item, Road)
             and self.activePlayer == self.players[0]
             and self.initialPlacementDirection == -1 ):
                self.stage = Stages.roll
                self._activeCountdown = Countdown(60)
            elif isinstance(item, Road):
                self.nextPlayer()
                self.activePlayer.add(Settlement())
                self._activeCountdown = Countdown(60)
            else:
                assert isinstance(item, Settlement)
                self.activePlayer.add(Road())
                self._activeCountdown = Countdown(60)
        else:
            assert self.stage == Stages.playerTurn

    @allowedDuring(Stages.roll)
    def onDiceRoll(self, rollValue):
        if rollValue == 7:
            if [len(player.cards) > 7 for player in self.players]:
                self.stage = Stages.sevenRolledDiscard
            else:
                self.stage = Stages.rolledRobberPlacement
        else:
            self.stage = Stages.cardHarvest

    @allowedDuring(Stages.sevenRolledDiscard)
    def onDiscard(self, player):
        if not [len(player.cards) > 7 for player in self.players]:
            self.stage = rolledRobberPlacement

    @allowedDuring(Stages.cardHarvest)
    def onCardHarvestOver(self):
        self.stage = playerTurn

    def onPlayerPointChange(self, player):
        if player.points >= 10:
            self.stage = gameOver


class Settlement(object):
    def __init__(self):
        self.owner = None
        self.location = None

class City(Settlement): pass

class Road(object):
    def __init__(self):
        self.owner = None
        self.location = None

class Robber(object): pass

class Terrain(object): pass

class Mountain(Terrain): pass
class Mud(Terrain): pass
class Wheat(Terrain): pass
class Grass(Terrain): pass
class Forest(Terrain): pass
class Desert(Terrain): pass

terrainClasses = [Wheat]*4 + [Mud]*3 + [Mountain]*3 + [Grass]*4 + [Forest]*4 + [Desert]

class Pip(object):
    def __init__(self, value):
        self.value = value

class Board(object):
    '''
    The .tiles attribute is laid out graphically like so:

                   [12]
            [ 8]          [11]
      [10]         [ 3]         [16]
            [ 2]          [ 5]
      [ 9]         [ 1]         [15]
            [ 4]          [ 7]
      [14]         [ 6]         [19]
            [13]          [17]
                   [18]

    '''
    # this is the order to walk around the mapmodel so that it results
    # in a clockwise spiral, starting at 18
    spiralWalk = [18,13,14,9,10,8,12,11,16,15,19,17,6,4,2,3,5,7,1]

    # graphical positions relative to the center tile, given in order
    # of the spiral walk
    graphicalPositions = [ (0,-4),  (-1,-3),
                           (-2,-2), (-2,0),
                           (-2,2),  (-1,3),
                           (0,4),   (1,3),
                           (2,2),   (2,0),
                           (2,-2),  (1,-3),
                           (0,-2),  (-1,-1),
                           (-1,1),  (0,2),
                           (1,1),   (1,-1),
                           (0,0)
                         ]
                           
    def __init__(self):
        pips = [Pip(i) for i in [5,2,6,3,8,10,9,12,11,4,8,10,9,4,5,6,3,11]]

        random.shuffle(terrainClasses)
        self.tiles = []
        mapmodel.build()
        for i, cls in enumerate(terrainClasses):
            tile = mapmodel.allTiles[Board.spiralWalk[i]-1]
            tile.graphicalPosition = Board.graphicalPositions[i]
            tile.terrain = cls()
            if cls != Desert:
                tile.pip = pips.pop(0)
            self.tiles.append(tile)

        events.post('BoardCreated', self)

class Game(object):
    def __init__(self):
        self.state = GameState()
        self.board = None

    def onBoardCreated(self, board):
        self.board = board

class Player(object):
    def __init__(self, identifier):
        self.identifier = identifier
        i = int(identifier)
        self.color = (50*i, 10, (255-40*i))
        self.stuff = []
        self.latestItem = None
        self.activeItem = None
        events.registerListener(self)

    def __str__(self):
        return '<Player %s>' % str(self.identifier)
    def __repr__(self):
        return str(self)

    def add(self, item):
        item.owner = self
        self.stuff.append(item)
        self.activeItem = item
        events.post('PlayerPlacing', self, item)

    def findFreeCornersForSettlement(self):
        freeCorners = []
        for c in mapmodel.allCorners:
            settledPeers = [corner for corner in c.getPeers()
                            if corner.stuff]
            if not settledPeers and not c.stuff:
                freeCorners.append(c)
        return freeCorners
        
    def findFreeEdgesOfSettlement(self, settlement):
        corner = settlement.location
        edges = corner.getEdges()
        return [e for e in edges if not e.stuff]

class HumanPlayer(Player):

    def onClickCorner(self, corner):
        if game.state.activePlayer == self:
            if self.activeItem and isinstance(self.activeItem, Settlement):
                corner.add(self.activeItem)
                self.latestItem = self.activeItem
                self.activeItem = None

    def onClickEdge(self, edge):
        if game.state.activePlayer == self:
            if self.activeItem and isinstance(self.activeItem, Road):
                edge.add(self.activeItem)
                self.latestItem = self.activeItem
                self.activeItem = None

    def onPlayerPlacing(self, player, item):
        if game.state.activePlayer == self:
            if game.state.stage == Stages.initialPlacement:
                if isinstance(self.activeItem, Settlement):
                    corners = self.findFreeCornersForSettlement()
                    events.post('HintLightCorners', corners)
                if isinstance(self.activeItem, Road):
                    edges = self.findFreeEdgesOfSettlement(self.latestItem)
                    events.post('HintLightEdges', edges)

class CPUPlayer(Player):
    def doInitialPlacement(self):
        if isinstance(self.activeItem, Settlement):
            corners = self.findFreeCornersForSettlement()
            c = corners[0]
            c.add(self.activeItem)
        elif isinstance(self.activeItem, Road):
            edges = self.findFreeEdgesOfSettlement(self.latestItem)
            e = edges[0]
            e.add(self.activeItem)
        self.latestItem = self.activeItem
        self.activeItem = None

    def onPlayerPlacing(self, player, item):
        if game.state.activePlayer == self:
            if game.state.stage == Stages.initialPlacement:
                self.doInitialPlacement()

game = None

def init():
    global game
    game = Game()

if __name__ == '__main__':
    init()
