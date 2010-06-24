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
    preRoll,
    sevenRolledDiscard,
    preRollRobberPlacement,
    postRollRobberPlacement,
    preRollChooseVictim,
    postRollChooseVictim,
    cardHarvest,
    playerTurn,
    gameOver,
    ) = [x[:-1] for x in shlex.split('''
    waitingForPlayers,
    setup,
    initialPlacement,
    preRoll,
    sevenRolledDiscard,
    preRollRobberPlacement,
    postRollRobberPlacement,
    preRollChooseVictim,
    postRollChooseVictim,
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
                print 'EVENT NOT ALLOWED', fn.__name__, game.state.stage
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

        if self.stage == Stages.preRoll:
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
                self.stage = Stages.preRoll
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
            if item.owner.points >= 10:
                self.stage = Stages.gameOver

    @allowedDuring(Stages.preRoll)
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
                self.stage = Stages.postRollRobberPlacement
                self.activePlayer.placeRobber()
        else:
            self.stage = Stages.cardHarvest

    @allowedDuring(Stages.sevenRolledDiscard)
    def onDiscard(self, player):
        self.awaitingDiscard.remove(player)
        if self.awaitingDiscard:
            return # someone still needs to discard
        self.stage = Stages.postRollRobberPlacement
        self.activePlayer.placeRobber()

    @allowedDuring(Stages.setup, Stages.preRollRobberPlacement,
                   Stages.postRollRobberPlacement)
    def onRobberPlaced(self, robber):
        if self.stage == Stages.setup:
            return
        if self.stage == Stages.postRollRobberPlacement:
            self.stage = Stages.postRollChooseVictim
        elif self.stage == Stages.preRollRobberPlacement:
            self.stage = Stages.preRollChooseVictim

    @allowedDuring(Stages.preRollChooseVictim, Stages.postRollChooseVictim)
    def onRobRequest(self, thief, victim):
        if thief == self.activePlayer:
            if victim.cards:
                card = random.choice(victim.cards)
                victim.cards.remove(card)
                thief.cards.append(card)
                events.post('Rob', thief, victim, card)
            if self.stage == Stages.postRollChooseVictim:
                self.stage = Stages.playerTurn
            elif self.stage == Stages.preRollChooseVictim:
                self.stage = Stages.preRoll

    @allowedDuring(Stages.preRollChooseVictim, Stages.postRollChooseVictim)
    def onSkipRobRequest(self, thief):
        if thief != self.activePlayer:
            return
        if self.stage == Stages.preRollChooseVictim:
            self.stage = Stages.preRoll
        elif self.stage == Stages.postRollChooseVictim:
            self.stage = Stages.playerTurn

    @allowedDuring(Stages.playerTurn)
    def onChooseTwoCardsRequest(self, player, cardClasses):
        if player == self.activePlayer:
            cards = []
            for cls in cardClasses:
                card = cls()
                cards.append(card)
                player.cards.append(card)
            events.post('ChooseTwoCards', player, cards)

    @allowedDuring(Stages.playerTurn)
    def onMonopolyRequest(self, player, cardClass):
        print '      In MONO'
        if player == self.activePlayer:
            events.post('Monopoly', player, cardClass)

    @allowedDuring(Stages.cardHarvest)
    def onCardHarvestOver(self):
        self.stage = Stages.playerTurn

    def onPlayerDrewVictoryCard(self, player, card):
        if player.points >= 10:
            self.stage = Stages.gameOver

    @allowedDuring(Stages.playerTurn)
    def onTurnFinishRequest(self, player):
        if player == self.activePlayer:
            self.nextPlayer()
            self.stage = Stages.preRoll

debugRolls = [(1,2), (4,4), (2,1), (2,1), (6,6)]
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
            or game.state.stage not in [Stages.preRoll]
            ):
            print 'illegal dice roll request', player
        else:
            print 'Dice roll:', a, b
            events.post('DiceRoll', a, b)
        

class Robber(object):
    def __init__(self):
        events.registerListener(self)
        self._tile = None

    @allowedDuring(Stages.postRollRobberPlacement, Stages.preRollRobberPlacement)
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
    cost = [Grain, Grain, Stone, Stone, Stone]
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
    maxPerPlayer = 13 #TODO check this
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

class Soldier(VictoryCard):
    def action(self, player):
        if game.state.stage == Stages.preRoll:
            game.state.stage = Stages.preRollRobberPlacement
        else:
            game.state.stage = Stages.postRollRobberPlacement
        player.placeRobber()

class YearOfPlenty(VictoryCard):
    def action(self, player):
        if game.state.stage != Stages.playerTurn:
            raise Exception('should only play during player turn')
        events.post('ShowPlayerChooseTwoCards', player)

class Monopoly(VictoryCard):
    def action(self, player):
        if game.state.stage != Stages.playerTurn:
            raise Exception('should only play during player turn')
        events.post('ShowMonopoly', player)


# TODO: use the official distribution
allVictoryCardClasses = [Monopoly, Soldier, Soldier, Soldier, Cathedral, University, Soldier, YearOfPlenty, Monopoly]

terrainClasses = [Wheat]*4 + [Mud]*3 + [Mountain]*3 + [Grass]*4 + [Forest]*4 + [Desert]

class Pip(object):
    def __init__(self, value):
        self.value = value

class Port(tuple):
    def __hash__(self):
        return id(self)

    def __repr__(self):
        if self[0]:
            return '<'+ str(self[0].__name__) + '/' + str(self[1]) + '>'
        else:
            return '<'+ str(self[0]) + '/' + str(self[1]) + '>'


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

        self.ports = [Port((None,3)), Port((None,3)),
                      Port((None,3)), Port((None,3)),
                      Port((Grain,2)), Port((Brick,2)),
                      Port((Stone,2)), Port((Sheep,2)),
                      Port((Wood,2))]
        random.shuffle(self.ports)

        self.layOutPorts()

        events.post('BoardCreated', self)

    def layOutPorts(self):
        positions = [(36,37), (39,40), (48,50),
                     (41,42), (34,35), (43,45),
                     (53,54), (25,27), (28,30),
                    ]
        # TODO, don't hardcode this, calculate it.  All it would take
        #       for this to break would be the allCorners list changing order
        for i, port in enumerate(self.ports):
            num1, num2 = positions[i]
            c1 = mapmodel.allCorners[num1-1]
            c2 = mapmodel.allCorners[num2-1]
            c1.port = port
            c2.port = port

    def populateGraphicalPositions(self):
        for i in range(len(self.tiles)):
            tile = mapmodel.allTiles[Board.spiralWalk[i]-1]
            tile.graphicalPosition = Board.graphicalPositions[i]

class Game(object):
    def __init__(self):
        self._largestArmyPlayer = None
        self._longestRoadPlayer = None
        self._longestRoadLength = 0
        self._largestArmySize = 0
        self.state = GameState(self)
        self.players = []
        self.dice = Dice()
        self.board = None

        events.registerListener(self)

    def getLargestArmyPlayer(self):
        self.calculateLargestArmy()
        return self._largestArmyPlayer
    largestArmyPlayer = property(getLargestArmyPlayer)

    def getLongestRoadPlayer(self):
        self.calculateLongestRoad()
        return self._longestRoadPlayer
    longestRoadPlayer = property(getLongestRoadPlayer)

    def calculateLargestArmy(self):
        for player in self.players:
            armySize = player.armySize()
            #print 'player', player, 'len', armySize
            if armySize > self._largestArmySize and armySize >= 3:
                self._largestArmySize = armySize
                self._largestArmyPlayer = player

    def calculateLongestRoad(self, newRoad=None):
        for player in self.players:
            roadLen = player.longestRoadLength()
            #print 'player', player, 'road len', roadLen
            if roadLen > self._longestRoadLength and roadLen >= 5:
                self._longestRoadLength = roadLen
                self._longestRoadPlayer = player
            

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
                        if not corner.settlement:
                            continue
                        owner = corner.settlement.owner
                        if isinstance(corner.settlement, City):
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
        self.playedVictoryCards = []
        self.victoryCardPlayedThisTurn = False
        self.victoryCardsBoughtThisTurn = []
        self.offer = []
        self.wants = []
        self.latestItem = None
        self.activeItem = None
        events.registerListener(self)

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
            if not item.location:
                # item was bought, but hasn't been set down yet
                continue
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
    allPoints = None
    visiblePoints = None

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

    def getHasLargestArmy(self):
        return game.largestArmyPlayer == self
    hasLargestArmy = property(getHasLargestArmy)

    def getHasLongestRoad(self):
        return game.longestRoadPlayer == self
    hasLongestRoad = property(getHasLongestRoad)

    def getPorts(self): #TODO
        ports = set()
        for s in self.smallSettlements + self.cities:
            if s.location.port:
                ports.add(s.location.port)
        defaultPort = Port((None,4))
        return list(ports) + [defaultPort]
    ports = property(getPorts)

    def armySize(self):
        return len( [c for c in self.playedVictoryCards
                     if isinstance(c, Soldier)] )

    def longestRoadLength(self):
        # a player's road network can be thought of as a 
        # (possibly disconnected) graph that can have cycles

        def visitRoad(road):
            edge = road.location
            if not edge:
                # player hasn't placed this road on the board yet
                return 0
            lCorner = edge.corners[0]
            rCorner = edge.corners[1]
            visitedEdges = [edge]
            lLen = 1 + max([walkLen(lCorner, e, visitedEdges)
                            for e in lCorner.edges])
            visitedEdges = [edge]
            rLen = 1 + max([walkLen(rCorner, e, visitedEdges)
                            for e in rCorner.edges])
            return max([lLen, rLen])

        def walkLen(fromCorner, edge, visitedEdges):
            if edge == None:
                # corners have 3 edges, but water-adjacent corners can have
                # one of the corners == None
                return 0
            if not edge.road:
                return 0
            if edge.road.owner != self:
                return 0
            if edge in visitedEdges:
                return 0
            toCorner = edge.otherCorner(fromCorner)
            visitedEdges = visitedEdges[:]
            visitedEdges.append(edge)

            return 1 + max([walkLen(toCorner, e, visitedEdges)
                            for e in toCorner.edges])

        if not self.roads:
            return 0
        return max([visitRoad(r) for r in self.roads])

    def add(self, item):
        if isinstance(item, VictoryCard):
            self.victoryCards.append(item)
            self.victoryCardsBoughtThisTurn.append(item)
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

    def getVictoryCardOfClass(self, victoryCardClass):
        for c in self.victoryCards:
            if isinstance(c, victoryCardClass):
                return c
        return None

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

    @allowedDuring(Stages.playerTurn, Stages.preRoll)
    def onPlayVictoryCardRequest(self, player, victoryCardClass):
        if player != self or self != game.state.activePlayer:
            return

        foundCard = None
        for vcard in self.victoryCards:
            if isinstance(vcard, victoryCardClass):
                foundCard = vcard
                break
        if not foundCard:
            events.post('Error', 'Player does not have requested card.')
            return
        if not hasattr(foundCard, 'action'):
            events.post('Error', 'Card has no associated action.')
            return
        if self.victoryCardPlayedThisTurn:
            events.post('Error', 'Only one victory card per turn.')
            return
        if foundCard in self.victoryCardsBoughtThisTurn:
            events.post('Error', 'Victory card was bought this turn')
            return
        if (game.state.stage == Stages.preRoll
            and not victoryCardClass == Soldier):
            events.post('Error', 'Only soldier cards during pre-roll.')
            return

        self.victoryCardPlayedThisTurn = True
            
        self.victoryCards.remove(foundCard)
        self.playedVictoryCards.append(foundCard)

        foundCard.action(self)

    def placeRobber(self):
        self.activeItem = game.board.robber
        events.post('PlayerPlacing', self, self.activeItem)

    def findPossibleVictims(self):
        victims = set()
        for c in game.board.robber.tile.corners:
            if not c.settlement:
                continue
            if c.settlement.owner != self:
                victims.add(c.settlement.owner)
        return list(victims)

    def findFreeCornersForSettlement(self):
        freeCorners = []
        for c in mapmodel.allCorners:
            if c.settlement:
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
                if not e or not e.road:
                    continue
                if e.road.owner == self:
                    connectedCorners.append(corner)
        return connectedCorners

    def filterUnblockedCorners(self, corners):
        # remove any corner that is adjacent to a settled corner
        return [corner for corner in corners
                if not
                       [peer for peer in corner.getPeers()
                        if peer.settlement]
               ]
        
    def findFreeEdgesOfSettlement(self, settlement):
        corner = settlement.location
        edges = corner.getEdges()
        return [e for e in edges if not e.road]

    def findFreeEdgesForRoad(self):
        freeEdges = []
        for e in mapmodel.allEdges:
            # if an edge has a road it is definitely not free
            if e.road:
                continue

            for corner in e.corners:
                # i can build on an edge next to my house
                if corner.settlement:
                    settlement = corner.settlement
                    if settlement.owner == self:
                        freeEdges.append(e)
                        break
                # i can build on an edge next to my road, as long
                # as there's no opponent house in the way
                else:
                    otherEdges = [edge for edge in corner.edges
                                  if edge != e and edge != None]
                    for otherEdge in otherEdges:
                        if otherEdge.road:
                            if otherEdge.road.owner == self:
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

    def onMaritimeTrade(self, player, playerCards, portCards):
        if self == player:
            for card in playerCards:
                self.cards.remove(card)
            for card in portCards:
                self.cards.append(card)
        self.offer = []
        self.wants = []

    def onMonopolyGive(self, donor, receiver, cards):
        print 'Give seen'
        if self == receiver:
            print 'I got', cards
            for card in cards:
                self.cards.append(card)

    def onMonopoly(self, player, cardClass):
        if player == self:
            return
        stolen = [card for card in self.cards if isinstance(card, cardClass)]
        for card in stolen:
            self.cards.remove(card)
        events.post('MonopolyGive', self, player, stolen)



# -----------------------------------------------------------------------------
class HumanPlayer(Player):
    def onPlayerSet(self, newPlayer):
        if newPlayer == self:
            self.victoryCardPlayedThisTurn = False
            self.victoryCardsBoughtThisTurn = []

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
            for cls, howMany in toGive.items():
                for card in self.cards:
                    if card.__class__ == cls and card not in self.offer:
                        self.offer.append(card)
                        howMany -= 1
                        if howMany == 0:
                            break
                if howMany != 0:
                    events.post('Error', 'Player does not have enough cards')
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

    def onMaritimeTradeRequest(self, proposal):
        if game.state.activePlayer != self:
            return
        giveCards = proposal[0][:] #copy
        takeCardClasses = proposal[1][:] #copy
        print 'giveCards', giveCards
        print 'takeCardClasses', takeCardClasses
        # giveCards should be one card of any type
        if len(giveCards) != 1:
            events.post('Error', 'Maritime trades are for one card only')
            return
        # check that player has enough cards for the proposal
        print 'self offer', self.offer
        offerClass = self.offer[0].__class__ # should only be one class offered
        for card in self.offer:
            try:
                takeCardClasses.remove(card.__class__)
                if card.__class__ != offerClass:
                    raise ValueError('All offered cards should be same class')
            except ValueError:
                print 'fail maritime req', ex
                raise
        if takeCardClasses != []:
            print 'fail maritime req extra', takeCardClasses
            return

        # check the proposal is valid based on the porst the player can access
        foundPort = False
        for cardClass, howMany in self.ports:
            if len(proposal[1]) != howMany:
                continue
            if cardClass == None:
                foundPort = True
                break
            elif cardClass == proposal[1][0]:
                #all of them should be the same class
                foundPort = True
                break
        if not foundPort:
            events.post('Error', 'No maritime port to take the trade')
            return

        events.post('MaritimeTrade', self, self.offer, giveCards)


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

        if game.state.stage == Stages.preRoll:
            self.rollDice()
        if game.state.stage == Stages.playerTurn:
            events.post('TurnFinishRequest', self)
        if game.state.stage in [Stages.preRollChooseVictim,
                                Stages.postRollChooseVictim]:
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
