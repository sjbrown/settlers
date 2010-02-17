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
        events.Event.__init__(self, newStage)
        self.newStage = newStage
        print self
    def __repr__(self):
        return '<StageChange Event %s>' % self.newStage
    __str__ = __repr__

class Stages:
    (
    waitingForPlayers,
    setup,
    initialPlacement,
    preRollSoldier,
    roll,
    sevenRolledDiscard,
    rolledRobberPlacement,
    soldierCard,
    chooseVictim,
    cardHarvest,
    playerTurn,
    gameOver,
    ) = [x[:-1] for x in shlex.split('''
    waitingForPlayers,
    setup,
    initialPlacement,
    preRollSoldier,
    roll,
    sevenRolledDiscard,
    rolledRobberPlacement,
    soldierCard,
    chooseVictim,
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
            #print 'called ', fn
            #print 'stage was', self.stage
            #print 'supposed to be in', allowedStages
            if self.stage not in allowedStages:
                raise EventNotAllowedAtThisStage(fn.__name__, self.stage, allowedStages)
            retval = fn(self, *args)
            return retval
        wrappedfn.__name__ = fn.__name__
        return wrappedfn
    return decoratr
        

class GameState(object):
    def __init__(self, game):
        self.game = game
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
        idx = self.game.players.index(self.activePlayer)
        if self.stage == Stages.initialPlacement:
            if idx == len(self.game.players)-1 and self.initialPlacementDirection == 1:
                self.initialPlacementDirection = -1
                return #keep the player the same
            if idx == 0 and self.initialPlacementDirection == -1:
                assert False, 'Should never get here'
            idx += self.initialPlacementDirection
        else:
            idx += 1
            idx %= len(self.game.players)
        self.activePlayer = self.game.players[idx]
        print 'NExT PLAYER', self.activePlayer

    @allowedDuring(Stages.waitingForPlayers)
    def onPlayerJoin(self, player):
        print 'p jed', player
        self.game.players.append(player)
        if len(self.game.players) == 4:
            self.stage = Stages.setup

    def onCountdownOver(self):
        self._activeCountdown = None
        if self.stage == Stages.initialPlacement:
            position = self.activePlayer.activeItem.findBestPosition()
            self.activePlayer.activeItem.place(position)

        if self.stage == Stages.preRollSoldier:
            # TODO ...force a roll
            pass

    @allowedDuring(Stages.setup)
    def onBoardCreated(self, board):
        self.activePlayer = self.game.players[0]
        self.activePlayer.add(Settlement())
        self.stage = Stages.initialPlacement
        self._activeCountdown = Countdown(60)

    @allowedDuring(Stages.initialPlacement, Stages.playerTurn)
    def onItemPlaced(self, item):
        if self.stage == Stages.initialPlacement:
            if ( isinstance(item, Road)
             and self.activePlayer == self.game.players[0]
             and self.initialPlacementDirection == -1 ):
                self.stage = Stages.preRollSoldier
                self._activeCountdown = Countdown(60)
            elif isinstance(item, Road):
                self.nextPlayer()
                self.activePlayer.add(Settlement())
                self._activeCountdown = Countdown(60)
            elif isinstance(item, Settlement):
                self.activePlayer.add(Road())
                self._activeCountdown = Countdown(60)
            else:
                print 'FAIL'
        else:
            assert self.stage == Stages.playerTurn
            print 'NotImp'

    @allowedDuring(Stages.preRollSoldier)
    def onDiceRoll(self, rollValue):
        if rollValue == 7:
            if any([len(player.cards) > 7 for player in self.game.players]):
                self.stage = Stages.sevenRolledDiscard
            else:
                self.stage = Stages.rolledRobberPlacement
                self.activePlayer.placeRobber()
        else:
            self.stage = Stages.cardHarvest

    @allowedDuring(Stages.sevenRolledDiscard)
    def onDiscard(self, player):
        if not [len(player.cards) > 7 for player in self.game.players]:
            self.stage = rolledRobberPlacement

    @allowedDuring(Stages.setup, Stages.rolledRobberPlacement, Stages.soldierCard)
    def onRobberPlaced(self, robber):
        if self.stage == Stages.setup:
            return
        self.stage = Stages.chooseVictim

    @allowedDuring(Stages.chooseVictim)
    def onRobRequest(self, thief, victim):
        if thief == self.activePlayer:
            if victim.cards:
                card = random.choice(victim.cards)
                victim.cards.remove(card)
                events.post('Rob', thief, victim, card)
            self.stage = Stages.playerTurn

    @allowedDuring(Stages.cardHarvest)
    def onCardHarvestOver(self):
        self.stage = Stages.playerTurn

    def onPlayerPointChange(self, player):
        if player.points >= 10:
            self.stage = gameOver

    @allowedDuring(Stages.playerTurn)
    def onTurnFinishRequest(self, player):
        if player == self.activePlayer:
            self.nextPlayer()
            self.stage = Stages.preRollSoldier

class Dice(object):
    def __init__(self):
        events.registerListener(self)
        self.lastRoll = None

    def onDiceRollRequest(self, player):
        import random
        a = random.randrange(1,7)
        b = random.randrange(1,7)
        self.lastRoll = (a,b)
        if player != game.state.activePlayer:
            print 'illegal dice roll request', player
        else:
            print 'Dice roll:', a, b
            events.post('DiceRoll', a+b)
        

class Robber(object):
    def __init__(self):
        events.registerListener(self)
        self._tile = None

    def onRobberPlaceRequest(self, player, tile):
        if player != game.state.activePlayer:
            print 'illegal robber place request', player
            return
        self.placeOnTile(tile)
        
    def placeOnTile(self, tile):
        if self._tile:
            self._tile.robber = None
        self._tile = tile
        self._tile.robber = self
        print 'Robber placed:', tile
        events.post('RobberPlaced', self)

    def getTile(self):
        return self._tile
    tile = property(getTile)


class Settlement(object):
    def __init__(self):
        self.owner = None
        self.location = None

class City(Settlement): pass

class Road(object):
    def __init__(self):
        self.owner = None
        self.location = None

class Card(object): pass
class Stone(Card): pass
class Brick(Card): pass
class Grain(Card): pass
class Sheep(Card): pass
class Wood(Card): pass

class Terrain(object): pass
class Desert(Terrain): pass
class Mountain(Terrain):
    def getCardClass(self):
        return Stone
class Mud(Terrain):
    def getCardClass(self):
        return Brick
class Wheat(Terrain):
    def getCardClass(self):
        return Grain
class Grass(Terrain):
    def getCardClass(self):
        return Sheep
class Forest(Terrain):
    def getCardClass(self):
        return Wood

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
        self.robber = Robber()
        mapmodel.build()
        for i, cls in enumerate(terrainClasses):
            tile = mapmodel.allTiles[Board.spiralWalk[i]-1]
            tile.graphicalPosition = Board.graphicalPositions[i]
            tile.terrain = cls()
            if cls == Desert:
                self.robber.placeOnTile(tile)
            else:
                tile.pip = pips.pop(0)
            self.tiles.append(tile)

        events.post('BoardCreated', self)

    def populateGraphicalPositions(self):
        for i in range(len(self.tiles)):
            tile = mapmodel.allTiles[Board.spiralWalk[i]-1]
            tile.graphicalPosition = Board.graphicalPositions[i]

class Game(object):
    def __init__(self):
        self.state = GameState(self)
        self.players = []
        self.dice = Dice()
        self.board = None

        events.registerListener(self)

    def onStageChange(self, newStage):
        if game.state.stage == Stages.setup:
            self.board = Board()
        if game.state.stage == Stages.cardHarvest:
            for tile in self.board.tiles:
                if tile.pip == None:
                    continue
                if tile.pip.value == sum(self.dice.lastRoll):
                    cardClass = tile.terrain.getCardClass()
                    for corner in tile.corners:
                        for settlement in corner.stuff:
                            owner = settlement.owner
                            if isinstance(settlement, City):
                                # Cities get 2 cards
                                cards = [cardClass(), cardClass()]
                            else:
                                # Regular settlements get 1 card
                                cards = [cardClass()]
                            events.post('Harvest', cards, tile, owner)
            events.post('CardHarvestOver')


class Player(object):
    def __init__(self, identifier):
        self.identifier = identifier
        i = int(identifier)
        self.color = (50*i, 10, (255-40*i))
        self.items = []
        self.cards = []
        self.latestItem = None
        self.activeItem = None
        events.registerListener(self)

    def __str__(self):
        return '<Player %s>' % str(self.identifier)
    def __repr__(self):
        return str(self)

    def add(self, item):
        item.owner = self
        self.items.append(item)
        self.activeItem = item
        events.post('PlayerPlacing', self, item)

    def placeRobber(self):
        self.activeItem = game.board.robber
        events.post('PlayerPlacing', self, self.activeItem)

    def findPossibleVictims(self):
        victims = set()
        for c in game.board.robber.tile.corners:
            if not c.stuff:
                continue
            settlement = c.stuff[0]
            if settlement.owner != self:
                victims.add(settlement.owner)
        return list(victims)

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

    def findFreeTilesForRobber(self):
        freeTiles = []
        for t in mapmodel.allTiles:
            if isinstance(t.terrain, Desert):
                continue
            if t.robber:
                continue
            freeTiles.append(t)
        return freeTiles
        

    def onHarvest(self, cards, sourceTile, recipient):
        if recipient == self:
            self.cards += cards

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
                if isinstance(self.activeItem, Robber):
                    tiles = self.findFreeTilesForRobber(self.latestItem)
                    events.post('HintLightTiles', tiles)

class CPUPlayer(Player):
    def doInitialPlacement(self):
        return self.doPlacement()

    def doPlacement(self):
        if isinstance(self.activeItem, Settlement):
            corners = self.findFreeCornersForSettlement()
            c = corners[0]
            c.add(self.activeItem)
        elif isinstance(self.activeItem, Road):
            edges = self.findFreeEdgesOfSettlement(self.latestItem)
            e = edges[0]
            e.add(self.activeItem)
        elif isinstance(self.activeItem, Robber):
            tiles = self.findFreeTilesForRobber()
            t = tiles[0]
            events.post('RobberPlaceRequest', self, t)
        self.latestItem = self.activeItem
        self.activeItem = None

    def rollDice(self):
        # might want to decide whether to use a Soldier Card here
        events.post('DiceRollRequest', self)

    def chooseVictim(self):
        opponents = self.findPossibleVictims()
        if opponents:
            victim = opponents[0]
            events.post('RobRequest', self, victim)
        else:
            print 'NotImplemented'

    def onPlayerPlacing(self, player, item):
        if game.state.activePlayer == self:
            if game.state.stage == Stages.initialPlacement:
                self.doInitialPlacement()
            else:
                self.doPlacement()

    def onStageChange(self, newStage):
        print self, 'sees new stage', newStage
        if game.state.activePlayer != self:
            return
        if game.state.stage == Stages.preRollSoldier:
            self.rollDice()
        if game.state.stage == Stages.playerTurn:
            events.post('TurnFinishRequest', self)
        if game.state.stage == Stages.chooseVictim:
            self.chooseVictim()

game = None

def init():
    global game
    game = Game()

if __name__ == '__main__':
    init()
