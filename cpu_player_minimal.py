'''
This is the minimal CPU player.  It's good for testing, but not much else
'''

import random
import events
import mapmodel
import catan
from catan import Stages, Player, Settlement, City, Road, Robber, Stone, Brick, Grain, Sheep, Wood, Desert, Mountain, Mud, Wheat, Grass, Forest, Cathedral, University, Soldier, YearOfPlenty, Monopoly

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
        if catan.game.state.activePlayer == self:
            if catan.game.state.stage == Stages.initialPlacement:
                self.doInitialPlacement()
            else:
                self.doPlacement()

    def onStageChange(self, newStage):
        print self, 'sees new stage', newStage
        self.offer = []
        self.wants = []
        if catan.game.state.stage == Stages.sevenRolledDiscard:
            self.discard()

        if catan.game.state.activePlayer != self:
            return

        if catan.game.state.stage == Stages.preRoll:
            self.rollDice()
        if catan.game.state.stage == Stages.playerTurn:
            events.post('TurnFinishRequest', self)
        if catan.game.state.stage in [Stages.preRollChooseVictim,
                                Stages.postRollChooseVictim]:
            self.chooseVictim()

    def onProposeTrade(self, player, toGive, toTake):
        if player != self and player == catan.game.state.activePlayer:
            if self.offer:
                return # already made an offer
            if not self.cards:
                return
            self.makeProposal(toGive, toTake)

'''
Here is a list of methods a Player class can choose to implement
    def onPlayerJoin(self, player):
    def onStageChange(self, newStage):
    def onPlayerSet(self, newPlayer):
    def onDiceRoll(self, d1, d2):
    def onDiscard(self, player):
    def onRobberPlaced(self, robber):
    def onRob(self, thief, victim, card):

    def onHarvest(self, cards, sourceTile, recipient):
    def onCardHarvestOver(self):

    def onPlayerPlacing(self, player, item):
    def onItemPlaced(self, item):
    def onPlayerDrewVictoryCard(self, player, card):

    def onProposeTrade(self, player, toGive, toTake):
    def onMaritimeTrade(self, player, playerCards, portCards):

    def onMonopolyGive(self, donor, receiver, cards):
    def onMonopoly(self, player, cardClass):

Here is a list of events that a Player class can send:
    TurnFinishRequest(player)
    DiceRollRequest(player)
    DiscardRequest(player, discards)
    RobberPlaceRequest(player, tile)
    RobRequest(thief, victim)
    SkipRobRequest(thief) # when the robber is not adjacent to an opponent
    BuyRequest(player, itemClass)
    ClickCorner(corner)
    ClickEdge(edge)

    ConfirmProposalRequest(opponent, proposal)
    MaritimeTradeRequest(proposal)

    PlayVictoryCardRequest(player, victoryCardClass)
    ChooseTwoCardsRequest(player, cardClasses) # Year of Plenty
    MonopolyRequest(player, cardClass)
'''
