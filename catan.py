#! /usr/bin/env python

import time
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
            events.Fire('CountdownOver')


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
    gameOver
    ) = range(10)
    
class TurnOptions:
    (
    playRobber,
    build,
    playYearOfPlenty,
    playMonopoly,
    trade
    ) = range(5)


class EventNotAllowedAtThisStage(Exception): pass

def allowedDuring(*allowedStages):
    def decoratr(fn):
        def wrappedfn(self, *args):
            print 'stage was', self.stage
            print 'supposed to be in', allowedStages
            if self.stage not in allowedStages:
                raise EventNotAllowedAtThisStage(fn.__name__, self.stage, allowedStage)
            print 'start with', args
            retval = fn(*args)
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

    def getActivePlayer(self):
        return self._activePlayer
    def setActivePlayer(self, player):
        self._activePlayer = player
        events.fire('PlayerSet', player)
    activePlayer = property(getActivePlayer, setActivePlayer)

    def getStage(self):
        return self._stage
    def setStage(self, stage):
        self._stage = stage
        events.fire('StageChange', stage)
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

    @allowedDuring(Stages.waitingForPlayers)
    def onPlayerJoin(self, player):
        self.players.append(player)
        if len(self.players) == 4:
            self.stage = Stages.setup
            self.board = Board()

    def onCountdownOver(self):
        self._activeCountdown = None
        if self.stage == Stages.initialPlacement:
            position = self.activePlayer.activeToken.findBestPosition()
            self.activePlayer.activeToken.place(position)

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
    def onTokenPlaced(self, token):
        if self.stage == Stages.initialPlacement:
            if ( isinstance(token, Road)
             and self.activePlayer == self.players[0]
             and self.initialPlacementDirection == -1 ):
                self.stage = Stages.roll
                self._activeCountdown = Countdown(60)
            elif isinstance(token, Road):
                self.nextPlayer()
                self.activePlayer.add(Settlement())
                self._activeCountdown = Countdown(60)
            else:
                assert isinstance(token, Settlement)
                self.activePlayer.add(Road())
                self._activeCountdown = Countdown(60)
        else:
            assert self.stage == Stages.playerTurn

    @allowedDuring(Stages.roll)
    def onDiceRoll(sef, rollValue):
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


class Settlement(object): pass
class City(Settlement): pass

class Road(object): pass

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
        self.board = Board()

game = None

def init():
    global game
    game = Game()

if __name__ == '__main__':
    init()
