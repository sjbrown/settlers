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
        def wrappedfn(*args):
            if not game:
                raise ValueError('Game must be initialized before a function'
                                 ' decorated with allowedDuring can be called')
            #print 'called ', fn
            #print 'supposed to be in', allowedStages
            if game.state.stage not in allowedStages:
                print 'EVENT NOT ALLOWED'
                events.post('EventNotAllowedAtThisStage', fn.__name__,
                                                 game.state.stage,
                                                 allowedStages)
                return
                #raise EventNotAllowedAtThisStage(fn.__name__,
                #                                 game.state.stage,
                #                                 allowedStages)
            retval = fn(*args)
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
        self.awaitingDiscard = []
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
    def onDiceRoll(self, d1, d2):
        rollValue = d1+d2
        if rollValue == 7:
            found = False
            for player in self.game.players:
                if player.mustDiscard():
                    found = True
                    self.awaitingDiscard.append(player)
            if found:
                self.stage = Stages.sevenRolledDiscard
            else:
                self.stage = Stages.rolledRobberPlacement
                self.activePlayer.placeRobber()
        else:
            self.stage = Stages.cardHarvest

    @allowedDuring(Stages.sevenRolledDiscard)
    def onDiscard(self, player):
        self.awaitingDiscard.remove(player)
        if self.awaitingDiscard:
            return # someone still needs to discard
        self.stage = Stages.rolledRobberPlacement
        self.activePlayer.placeRobber()

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
                thief.cards.append(card)
                events.post('Rob', thief, victim, card)
            self.stage = Stages.playerTurn

    @allowedDuring(Stages.chooseVictim)
    def onSkipRobRequest(self, thief):
        if thief == self.activePlayer:
            self.stage = Stages.playerTurn

    @allowedDuring(Stages.cardHarvest)
    def onCardHarvestOver(self):
        self.stage = Stages.playerTurn

    def onPlayerPointChange(self, player):
        if player.points >= 10:
            self.stage = Stages.gameOver

    @allowedDuring(Stages.playerTurn)
    def onTurnFinishRequest(self, player):
        if player == self.activePlayer:
            self.nextPlayer()
            self.stage = Stages.preRollSoldier

debugRolls = [(1,2), (2,5), (2,1), (2,1), (6,6)]
class Dice(object):
    def __init__(self):
        events.registerListener(self)
        self.lastRoll = None

    def onDiceRollRequest(self, player):
        import random
        if debugRolls:
            a,b = debugRolls.pop(0)
        else:
            a = random.randrange(1,7)
            b = random.randrange(1,7)
        self.lastRoll = (a,b)
        if (player != game.state.activePlayer
            or game.state.stage not in [Stages.preRollSoldier]
            ):
            print 'illegal dice roll request', player
        else:
            print 'Dice roll:', a, b
            events.post('DiceRoll', a, b)
        

class Robber(object):
    def __init__(self):
        events.registerListener(self)
        self._tile = None

    @allowedDuring(Stages.rolledRobberPlacement, Stages.soldierCard)
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


class Card(object):
    def __str__(self):
        return '<Card %s %s>' % (self.__class__.__name__, id(self))
    __repr__ = __str__
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

class FiniteGameObject(object):
    '''A game object of which there are a finite amount
    eg, there are only 5 Settlements per player
    '''
    @staticmethod
    def takeOne(cls, player, attrName):
        '''A factory method which returns a new object of class 'cls', but
        first checks to see if there are any available
        '''
        if len(getattr(player, attrName)) >= cls.maxPerPlayer:
            raise LookupError('Player has the maximum number of %s' % attrName)
        return cls()

class Settlement(FiniteGameObject):
    cost = [Wood, Sheep, Grain, Brick]
    maxPerPlayer = 5 #TODO check this
    def __init__(self):
        self.owner = None
        self.location = None

    @classmethod
    def takeOne(cls, player):
        return FiniteGameObject.takeOne(cls, player, 'smallSettlements')

    @classmethod
    def canBeBought(cls, player):
        spots = player.findFreeCornersForSettlement()
        return bool(spots)

class City(Settlement):
    cost = [Grain, Grain, Grain, Stone, Stone]
    maxPerPlayer = 5 #TODO check this

    @classmethod
    def takeOne(cls, player):
        return FiniteGameObject.takeOne(cls, player, 'cities')

    @classmethod
    def canBeBought(cls, player):
        spots = [x.location for x in player.smallSettlements]
        return bool(spots)

class Road(FiniteGameObject):
    cost = [Wood, Brick]
    maxPerPlayer = 11 #TODO check this
    def __init__(self):
        self.owner = None
        self.location = None

    @classmethod
    def takeOne(cls, player):
        return FiniteGameObject.takeOne(cls, player, 'roads')

    @classmethod
    def canBeBought(cls, player):
        spots = player.findFreeEdgesForRoad()
        return bool(spots)

class VictoryCard(FiniteGameObject):
    cost = [Grain, Sheep, Stone]
    def __str__(self):
        return '<VictoryCard %s %s>' % (self.__class__.__name__, id(self))
    __repr__ = __str__

    @classmethod
    def takeOne(cls, player):
        # TODO: shuffle
        try:
            subclass = allVictoryCardClasses.pop(0)
        except IndexError:
            raise IndexError('There are no more victory cards in the deck')
        return subclass()

class PointCard(VictoryCard): pass

class Cathedral(PointCard): pass
class University(PointCard): pass

class Soldier(VictoryCard): pass
class YearOfPlenty(VictoryCard): pass
class Monopoly(VictoryCard): pass

# TODO: use the official distribution
allVictoryCardClasses = [Cathedral, University, Soldier, YearOfPlenty, Monopoly]

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

    def calculateLongestRoad(self, newRoad):
        print "NOT IMPLEMENTED calculateLongestRoad"

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

    def onItemPlaced(self, item):
        if isinstance(item, Road):
            self.calculateLongestRoad(item)


class Player(object):
    colors = [ (250,0,0), (250,250,250), (250,150,0), (10,20,250) ]
    def __init__(self, identifier):
        self.identifier = identifier
        i = int(identifier)
        #self.color = (50*i, 10, (255-40*i))
        self.color = Player.colors[i-1]
        self.items = []
        self.cards = []
        self.victoryCards = []
        self.offer = []
        self.wants = []
        self.latestItem = None
        self.activeItem = None
        events.registerListener(self)
        self.hasLongestRoad = False
        self.hasLargestArmy = False

    def __str__(self):
        return '<Player %s>' % str(self.identifier)
    def __repr__(self):
        return str(self)

    def getProposal(self):
        offerClasses = [card.__class__ for card in self.offer]
        return [offerClasses, self.wants]
    proposal = property(getProposal)

    def getPoints(self):
        points = 0
        for item in self.items:
            if isinstance(item, Settlement):
                if isinstance(item, City):
                    points += 2
                else:
                    points += 1
        for vcard in self.victoryCards:
            if isinstance(vcard, PointCard):
                points += 1
        if self.hasLongestRoad:
            points += 2
        if self.hasLargestArmy:
            points += 2
        return points
    points = property(getPoints)

    def getRoads(self):
        return [item for item in self.items
                if isinstance(item, Road)]
    roads = property(getRoads)

    def getSmallSettlements(self):
        return [item for item in self.items
                if isinstance(item, Settlement)
                and not isinstance(item, City)]
    smallSettlements = property(getSmallSettlements)

    def getCities(self):
        return [item for item in self.items
                if isinstance(item, City)]
    cities = property(getCities)

    def add(self, item):
        if isinstance(item, VictoryCard):
            self.victoryCards.append(item)
            events.post('PlayerDrewVictoryCard', self, item)
        else:
            item.owner = self
            self.items.append(item)
            self.activeItem = item
            events.post('PlayerPlacing', self, item)

    def buy(self, itemClass):
        price, needs = self.takePrice(itemClass, self.cards)
        assert not needs

    def neededCardClasses(self, itemClass):
        handCopy = self.cards[:]
        price, neededCardClasses = self.takePrice(itemClass, handCopy)
        return neededCardClasses

    def takePrice(self, itemClass, cards):
        '''return (price, neededCardClasses)'''
        price = []
        neededCardClasses = []
        for cardClass in itemClass.cost:
            satisfiers = [card for card in cards
                          if card.__class__ == cardClass]
            if not satisfiers:
                neededCardClasses.append(cardClass)
                continue
            cards.remove(satisfiers[0])
            price.append(satisfiers[0])
        return price, neededCardClasses

    def mustDiscard(self):
        return len(self.cards) > 7

    @allowedDuring(Stages.playerTurn)
    def onBuyRequest(self, player, itemClass):
        if player != self or self != game.state.activePlayer:
            return
        needs = self.neededCardClasses(itemClass)
        if needs:
            events.post('PlayerCannotAfford', self, itemClass, needs)
            return
        if hasattr(itemClass, 'canBeBought'):
            if not itemClass.canBeBought(self):
                msg = '%s constraints not satisfied' % itemClass
                events.post('PlayerCannotBuy', self, itemClass, msg)
                return
        try:
            item = itemClass.takeOne(self)
        except LookupError, e:
            msg = str(e)
            events.post('PlayerCannotBuy', self, itemClass, msg)
            print msg
            return
        self.buy(itemClass)
        self.add(item)

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
            if c.stuff:
                continue
            freeCorners.append(c)
        print 'free', freeCorners
        freeCorners = self.filterUnblockedCorners(freeCorners)
        print 'free', freeCorners

        if game.state.stage == Stages.initialPlacement:
            return freeCorners

        freeCorners = self.filterRoadConnectedCorners(freeCorners)
        print 'free', freeCorners
        return freeCorners

    def findCornersForCity(self):
        corners = []
        for item in self.items:
            if isinstance(item, Settlement) and not isinstance(item, City):
                corners.append(item.location)
        return corners

    def filterRoadConnectedCorners(self, corners):
        connectedCorners = []
        for corner in corners:
            for e in corner.edges:
                print 'e', e, e.stuff
                if not e.stuff:
                    continue
                road = e.stuff[0]
                print 'road', e, e.stuff
                if road.owner == self:
                    connectedCorners.append(corner)
        return connectedCorners

    def filterUnblockedCorners(self, corners):
        # remove any corner that is adjacent to a settled corner
        return [corner for corner in corners
                if not
                       [peer for peer in corner.getPeers()
                        if peer.stuff]
               ]
        
    def findFreeEdgesOfSettlement(self, settlement):
        corner = settlement.location
        edges = corner.getEdges()
        return [e for e in edges if not e.stuff]

    def findFreeEdgesForRoad(self):
        freeEdges = []
        for e in mapmodel.allEdges:
            # if an edge has a road it is definitely not free
            if e.stuff:
                continue

            for corner in e.corners:
                # i can build on an edge next to my house
                if corner.stuff:
                    settlement = corner.stuff[0]
                    if settlement.owner == self:
                        freeEdges.append(e)
                        break
                # i can build on an edge next to my road, as long
                # as there's no opponent house in the way
                else:
                    otherEdges = [edge for edge in corner.edges
                                  if edge != e and edge != None]
                    for otherEdge in otherEdges:
                        if otherEdge.stuff:
                            road = otherEdge.stuff[0]
                            if road.owner == self:
                                freeEdges.append(e)
                                break
        return freeEdges

    def findFreeTilesForRobber(self):
        freeTiles = []
        for t in mapmodel.allTiles:
            if isinstance(t.terrain, Desert):
                continue
            if t.robber:
                continue
            freeTiles.append(t)
        return freeTiles
        
    @allowedDuring(Stages.sevenRolledDiscard)
    def onDiscardRequest(self, player, discards):
        if self != player:
            return
        print 'player %s discards %d from %d' %\
               (self, len(discards), len(self.cards))
        if not all([card in self.cards for card in discards]):
            print 'Player tried to discard cards that he did not own'
            return
        if not len(discards) == len(self.cards)/2:
            print 'Player tried to discard the wrong amout of cards'
            return
        for card in discards:
            self.cards.remove(card)
        events.post('Discard', self)

    def onHarvest(self, cards, sourceTile, recipient):
        if recipient == self:
            self.cards += cards

    def onConfirmProposal(self, player, opponent, playerCards, opponentCards):
        if self == player:
            for card in playerCards:
                self.cards.remove(card)
            for card in opponentCards:
                self.cards.append(card)
        elif self == opponent:
            for card in playerCards:
                self.cards.append(card)
            for card in opponentCards:
                self.cards.remove(card)
        self.offer = []
        self.wants = []



class HumanPlayer(Player):

    def onClickCorner(self, corner):
        if game.state.activePlayer != self:
            return
        if not self.activeItem:
            print 'NO ACTIVE ITEM!!!!!!!!!!!!!!!!!!'
            return
        if isinstance(self.activeItem, City):
            oldItem = corner.pop()
            assert isinstance(oldItem, Settlement)
            self.items.remove(oldItem)
            corner.add(self.activeItem)
            self.latestItem = self.activeItem
            self.activeItem = None
        elif isinstance(self.activeItem, Settlement):
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
        if player == self and game.state.activePlayer == self:
            if isinstance(self.activeItem, Settlement):
                if isinstance(self.activeItem, City):
                    corners = self.findCornersForCity()
                    events.post('HintLightCorners', corners)
                else:
                    corners = self.findFreeCornersForSettlement()
                    events.post('HintLightCorners', corners)
            if isinstance(self.activeItem, Road):
                if game.state.stage == Stages.initialPlacement:
                    edges = self.findFreeEdgesOfSettlement(self.latestItem)
                else:
                    edges = self.findFreeEdgesForRoad()
                events.post('HintLightEdges', edges)
            if isinstance(self.activeItem, Robber):
                tiles = self.findFreeTilesForRobber()
                events.post('HintLightTiles', tiles)


    def onProposeTrade(self, player, toGive, toTake):
        if player == self:
            self.offer = []
            for cls in toGive:
                for card in self.cards:
                    if card.__class__ == cls and card not in self.offer:
                        self.offer.append(card)
                        break
            self.wants = toTake

    def onConfirmProposalRequest(self, opponent, proposal):
        if game.state.activePlayer != self:
            return
        giveCardClasses = proposal[0][:] #copy
        takeCardClasses = proposal[1][:] #copy
        for card in opponent.offer:
            try:
                giveCardClasses.remove(card.__class__)
            except ValueError:
                print 'fail confirm'
                raise
        if giveCardClasses != []:
            print 'fail confirm'
            return
        for card in self.offer:
            try:
                takeCardClasses.remove(card.__class__)
            except ValueError:
                print 'fail confirm'
                raise
        if takeCardClasses != []:
            print 'fail confirm'
            return
        events.post('ConfirmProposal', self, opponent,
                    self.offer, opponent.offer)


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
            events.post('SkipRobRequest', self)

    def discard(self):
        if len(self.cards) <= 7:
            return
        half = len(self.cards)//2 # the floor is the proper behaviour
        discards = self.cards[:half]
        events.post('DiscardRequest', self, discards)

    def makeProposal(self, toGive, toTake):
        self.offer = [self.cards[0]]
        self.wants = [random.choice([Stone, Brick, Grain, Sheep, Wood])]
        events.post('ProposeTrade', self,
                    [card.__class__ for card in self.offer],
                    self.wants )

    def onPlayerPlacing(self, player, item):
        if game.state.activePlayer == self:
            if game.state.stage == Stages.initialPlacement:
                self.doInitialPlacement()
            else:
                self.doPlacement()

    def onStageChange(self, newStage):
        print self, 'sees new stage', newStage
        self.offer = []
        self.wants = []
        if game.state.stage == Stages.sevenRolledDiscard:
            self.discard()

        if game.state.activePlayer != self:
            return

        if game.state.stage == Stages.preRollSoldier:
            self.rollDice()
        if game.state.stage == Stages.playerTurn:
            events.post('TurnFinishRequest', self)
        if game.state.stage == Stages.chooseVictim:
            self.chooseVictim()

    def onProposeTrade(self, player, toGive, toTake):
        if player != self and player == game.state.activePlayer:
            if self.offer:
                return # already made an offer
            if not self.cards:
                return
            self.makeProposal(toGive, toTake)


game = None

def init():
    global game
    game = Game()

if __name__ == '__main__':
    init()
