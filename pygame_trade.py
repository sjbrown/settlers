#! /usr/bin/env python

from collections import defaultdict

import pygame

import events
import catan
from pygame_utils import *


#------------------------------------------------------------------------------
class TradeButton(SimpleTextButton):
    def __init__(self):
        SimpleTextButton.__init__(self, (150,50), 'TRADE')

    #----------------------------------------------------------------------
    def onMouseLeftDown(self, pos):
        if self.rect.collidepoint(pos):
            if catan.game.state.stage != catan.Stages.playerTurn:
                print "Can only trade during active player's turn"
                return
            events.post('ShowTrade')


#------------------------------------------------------------------------------
class QuitTradeButton(SimpleTextButton):
    def __init__(self, pos):
        EasySprite.__init__(self)
        Highlightable.__init__(self)
        events.registerListener(self)
        self.text = 'QUIT TRADE'
        self.rect = pygame.Rect(pos[0], pos[1], 100,12)
        self.image = EasySurface(self.rect.size)
        self.draw()

    def click(self):
        events.post('HideTrade')

#------------------------------------------------------------------------------
class ProposalMatchButton(SimpleTextButton):
    def __init__(self, parent, pos):
        EasySprite.__init__(self)
        Highlightable.__init__(self)
        events.registerListener(self)
        self.parent = parent
        self.opponent = None
        self.hidden = True
        self.text = 'Match'
        self.rect = pygame.Rect(pos[0], pos[1], 60,12)
        self.image = EasySurface(self.rect.size)
        self.draw()

    def click(self):
        if self.hidden:
            return
        if not (self.opponent and self.opponent.proposal):
            return
        self.parent.matchProposal(self.opponent.proposal)

#------------------------------------------------------------------------------
class MaritimeMatchButton(SimpleTextButton):
    def __init__(self, parent, pos):
        EasySprite.__init__(self)
        Highlightable.__init__(self)
        events.registerListener(self)
        self.parent = parent
        self.proposal = None
        self.hidden = True
        self.text = 'Match'
        self.rect = pygame.Rect(pos[0], pos[1], 60,12)
        self.image = EasySurface(self.rect.size)
        self.draw()

    def click(self):
        print 'maritime match clicked'
        if self.hidden:
            return
        if not self.proposal:
            print 'maritime match no proposal'
            return
        print 'maritime match proposal match.'
        self.parent.matchProposal(self.proposal)

#------------------------------------------------------------------------------
class ProposeConfirmButton(SimpleTextButton):
    def __init__(self, pos):
        EasySprite.__init__(self)
        Highlightable.__init__(self)
        events.registerListener(self)
        self.opponent = None
        self.proposal = None
        self.hidden = True
        self.text = 'Confirm'
        self.rect = pygame.Rect(pos[0], pos[1], 60,12)
        self.image = EasySurface(self.rect.size)
        self.draw()

    def click(self):
        if self.hidden:
            return
        if not (self.opponent and self.proposal):
            return
        events.post('ConfirmProposalRequest', self.opponent, self.proposal)

#------------------------------------------------------------------------------
class MaritimeConfirmButton(SimpleTextButton):
    def __init__(self, pos):
        EasySprite.__init__(self)
        Highlightable.__init__(self)
        events.registerListener(self)
        self.proposal = None
        self.hidden = True
        self.text = 'Confirm'
        self.rect = pygame.Rect(pos[0], pos[1], 60,12)
        self.image = EasySurface(self.rect.size)
        self.draw()

    def click(self):
        if self.hidden:
            return
        if not self.proposal:
            return
        events.post('MaritimeTradeRequest', self.proposal)

#------------------------------------------------------------------------------
class TradeGiveButton(CardAddButton):
    def __init__(self, parent, pos, cardClass):
        CardAddButton.__init__(self, parent, pos, cardClass, symbol='^')

    def click(self):
        playerCardsOfClass = self.cardSubset()
        self.parent.addCard(self.cardClass, playerCardsOfClass)

#------------------------------------------------------------------------------
class TradeTakeButton(CardAddButton):
    def __init__(self, parent, pos, cardClass):
        CardAddButton.__init__(self, parent, pos, cardClass, symbol='v')

    def click(self):
        self.parent.takeCard(self.cardClass)

#------------------------------------------------------------------------------
class TradeDisplay(EasySprite):
    singleton_guard = False
    def __init__(self):
        assert TradeDisplay.singleton_guard == False, 'TODO: make this be safely ignored, not blow up'
        TradeDisplay.singleton_guard = True
        EasySprite.__init__(self)
        events.registerListener(self)
        self.image = EasySurface( (380,180) )
        self.rect = self.image.get_rect()

        # TODO: i'm not really liking these collections living here. I should
        # probably just switch to inspecting human Player's .proposal
        # {cardClass: [card1, card2, ...], ...}
        self._cardsToGive = {}
        # {cardClass1: 3, cardClass2: 1, ...}
        self._cardClassesToTake = defaultdict(lambda:0)

        self.giveButtons = {}
        self.takeButtons = {}

        self.textButtons = [QuitTradeButton((180,160))]
        self.matchButtons = [ ProposalMatchButton(self, (0,0)),
                              ProposalMatchButton(self, (0,0)),
                              ProposalMatchButton(self, (0,0)),]
        self.confirmButtons = [ ProposeConfirmButton((0,0)),
                                ProposeConfirmButton((0,0)),
                                ProposeConfirmButton((0,0)),]
        self.maritimeMatchButtons = [
                              MaritimeMatchButton(self, (0,0)),
                              MaritimeMatchButton(self, (0,0)),
                              MaritimeMatchButton(self, (0,0)),
                              MaritimeMatchButton(self, (0,0)),
                              MaritimeMatchButton(self, (0,0)),
                              MaritimeMatchButton(self, (0,0)),
                              ]
        self.maritimeConfirmButtons = [
                                MaritimeConfirmButton((0,0)),
                                MaritimeConfirmButton((0,0)),
                                MaritimeConfirmButton((0,0)),
                                MaritimeConfirmButton((0,0)),
                                MaritimeConfirmButton((0,0)),
                                MaritimeConfirmButton((0,0)),
                                MaritimeConfirmButton((0,0)),
                                ]
        self.drawBg()
        self.drawCards()
        self.drawOpponents()
        self.drawButtons()

        self.dirty = True
    
    #----------------------------------------------------------------------
    def reset(self):
        # {cardClass: [card1, card2, ...], ...}
        self._cardsToGive = {}
        # {cardClass1: 3, cardClass2: 1, ...}
        self._cardClassesToTake = defaultdict(lambda:0)

        self.dirty = True

    #----------------------------------------------------------------------
    def propose(self):
        cardClassesToGive = {}
        for cardClass, cardList in self._cardsToGive.items():
            cardClassesToGive[cardClass] = len(cardList)
        print 'to give', cardClassesToGive
        print 'to take', self._cardClassesToTake
        events.post('ProposeTrade', catan.game.state.activePlayer,
                    cardClassesToGive, self._cardClassesToTake)

    #----------------------------------------------------------------------
    def matchProposal(self, proposal):
        '''Human player matches the proposal put forward by an opponent
        (or by a maritime trade port)
        '''
        toGive, toTake = proposal
        newCardsToGive = {}
        newCardClassesToTake = defaultdict(lambda:0)
        # TODO: asDict returns a dict of class=>list items because doing
        # dict(group_cards(...)) makes all the items empty for some reason
        cardDict = group_cards(catan.game.state.activePlayer.cards, asDict=True)
        print 'togive', toGive
        print 'totake', toTake
        print cardDict
        try:
            for cls in toTake:
                matchingCards = cardDict[cls]
                card = matchingCards.pop()
                cardList = newCardsToGive.setdefault(cls, [])
                cardList.append(card)
        except (StopIteration, KeyError), ex:
            print 'there werent enough cards of that class'
            print 'ex', ex
            print 'exargs', ex.args
            return # there weren't enough cards of that class
        for x in toGive:
            #TODO: this is a hack until i standardize on proposal datastruct
            if type(x) == type:
                #it's a class
                newCardClassesToTake[x] += 1
            else:
                newCardClassesToTake[x.__class__] += 1
        self._cardsToGive = newCardsToGive
        self._cardClassesToTake = newCardClassesToTake
        self.propose()
        self.dirty = True

    #----------------------------------------------------------------------
    def matchesProposal(self, proposal):
        opponentGive, opponentTake = proposal
        opponentGive = opponentGive[:] #copy
        opponentTake = opponentTake[:] #copy
        print '----'
        #print 'op give', opponentGive
        #print 'self take', self._cardClassesToTake
        #print 'op take', opponentTake
        #print 'self give', self._cardsToGive
        try:
            for cardClass in self._cardsToGive:
                for card in self._cardsToGive[cardClass]:
                    opponentTake.remove(cardClass)
            for cardClass, howMany in self._cardClassesToTake.items():
                for i in range(howMany):
                    #TODO: this is a hack until i standardize on proposal datastruct
                    if type(opponentGive[0]) == type:
                        #it's a class
                        opponentGive.remove(cardClass)
                    else:
                        card = [x for x in opponentGive
                                if x.__class__ == cardClass][0]
                        opponentGive.remove(card)
        except (ValueError, IndexError), ex:
            print 'ValueError', ex, ex.args
            return False
        #print 'op give', opponentGive
        #print 'op take', opponentTake
        if opponentGive != [] or opponentTake != []:
            return False
        return True

    #----------------------------------------------------------------------
    def addCard(self, cardClass, playerCardsOfClass):
        if self._cardClassesToTake.get(cardClass):
            self._cardClassesToTake[cardClass] -= 1
        else:
            given = self._cardsToGive.get(cardClass, [])
            ungiven = playerCardsOfClass.difference(set(given))
            if not ungiven:
                return
            cardList = self._cardsToGive.setdefault(cardClass, [])
            cardList.append(ungiven.pop())
        self.propose()
        self.dirty = True

    #----------------------------------------------------------------------
    def takeCard(self, cardClass):
        if self._cardsToGive.get(cardClass):
            self._cardsToGive[cardClass].pop()
            if not self._cardsToGive[cardClass]:
                del self._cardsToGive[cardClass]
        else:
            self._cardClassesToTake[cardClass] += 1
        self.propose()
        self.dirty = True

    #----------------------------------------------------------------------
    def drawBg(self):
        self.image.fill( (0,0,20) )
        r = self.rect.move(-self.x,-self.y)
        pygame.draw.rect(self.image, blue, r, 8)
        pygame.draw.rect(self.image, (200,200,255), r, 1)

    #----------------------------------------------------------------------
    def drawButtons(self):
        for button in self.textButtons:
            button.update()
            self.image.blit(button.image, button.rect)

        for button in self.giveButtons.values():
            self.image.blit(button.image, button.rect)
            cards = self._cardsToGive.get(button.cardClass, [])
            howMany = len(cards)
            txtImg = font_render(str(howMany))
            pos = vect_add(button.rect.midtop, (0,-5))
            self.image.blit(txtImg, pos)

        for button in self.takeButtons.values():
            self.image.blit(button.image, button.rect)
            howMany = self._cardClassesToTake[button.cardClass]
            txtImg = font_render(str(howMany))
            pos = vect_add(button.rect.midbottom, (0,5))
            self.image.blit(txtImg, pos)

    #----------------------------------------------------------------------
    def drawCards(self):
        classes = [catan.Stone, catan.Brick, catan.Grain, catan.Sheep,
                   catan.Wood]
        x = 40
        y = 100
        for cls in classes:
            givePos = vect_add((x,y), (0, -25))
            self.giveButtons[cls] = TradeGiveButton(self, givePos, cls)

            takePos = vect_add((x,y), (0, 30))
            self.takeButtons[cls] = TradeTakeButton(self, takePos, cls)

            givenCards = self._cardsToGive.get(cls, [])
            group = [card for card in catan.game.state.activePlayer.cards
                     if isinstance(card, cls)
                     and card not in givenCards]

            draw_cards(group, self.image, x, y, 2, 3, number=True)
            x += 30

    #----------------------------------------------------------------------
    def drawOpponents(self):
        opponents = catan.game.players[:]
        opponents.remove(catan.game.state.activePlayer)
        padX, padY = 15, 5
        for i, opponent in enumerate(opponents):
            # draw the opponent's identifier
            x = padX + 60*i
            y = padY
            txtImg = font_render(str(opponent.identifier),
                                 color=opponent.color)
            self.image.blit(txtImg, (x, y))

            # draw the opponent's proposed trade
            cButton = self.confirmButtons[i]
            mButton = self.matchButtons[i]

            if not (opponent.offer or opponent.wants):
                cButton.hidden = True
                mButton.hidden = True
                continue
            classes = [catan.Stone, catan.Brick, catan.Grain, catan.Sheep,
                       catan.Wood]

            # draw "give" cards
            cards = opponent.offer
            cardGroups = group_cards(cards)
            for cls, group in cardGroups:
                xoffset = x + classes.index(cls)*8
                draw_cards(group, self.image, xoffset, y+10, 0,0, number=True)

            # draw "want" cards
            cardClasses = opponent.wants
            cards = [cls() for cls in cardClasses]
            cardGroups = group_cards(cards)
            for cls, group in cardGroups:
                xoffset = x + classes.index(cls)*8
                draw_cards(group, self.image, xoffset, y+5, 0,0, number=True)

            # draw proposematch button
            mButton.hidden = False
            mButton.opponent = opponent
            mButton.x = x
            mButton.y = y+40
            mButton.update()
            self.image.blit(mButton.image, mButton.rect)

            # draw proposeconfirm button
            if self.matchesProposal(opponent.proposal):
                cButton.hidden = False
                cButton.opponent = opponent
                cButton.proposal = opponent.proposal
                cButton.x = x
                cButton.y = y+52
                cButton.update()
                self.image.blit(cButton.image, cButton.rect)

    #----------------------------------------------------------------------
    def drawMaritime(self):
        padX, padY = 215, 5
        for i, port in enumerate(catan.game.state.activePlayer.ports):
            portCardClass, portAmt = port
            x = padX + 60*i
            y = padY
            identifier = str(portAmt)+':1' # '4:1' or '2:1'
            if portCardClass:
                identifier = portCardClass.__name__[0] + identifier
            txtImg = font_render(identifier, color=blue)
            self.image.blit(txtImg, (x, y))

            playerOffer = []
            # if the player has offered some cards take the first group of 4
            cardGroups = group_cards(catan.game.state.activePlayer.offer)
            for cls, group in cardGroups:
                group = list(group)
                if len(group) >= portAmt:
                    playerOfferClass = cls
                    playerOffer = group[:portAmt]
            # if the player has cards in their hand, take the first group of 4
            if not playerOffer:
                cardGroups = group_cards(catan.game.state.activePlayer.cards)
                for cls, group in cardGroups:
                    group = list(group)
                    if len(group) >= portAmt:
                        playerOfferClass = cls
                        playerOffer = group[:portAmt]

            # draw the trader's proposed trade
            cButton = self.maritimeConfirmButtons[i]
            mButton = self.maritimeMatchButtons[i]

            if not playerOffer:
                cButton.hidden = True
                continue

            classes = [catan.Stone, catan.Brick, catan.Grain, catan.Sheep,
                       catan.Wood]
            xoffset = x + classes.index(playerOfferClass)*8
            draw_cards(playerOffer, self.image, xoffset, y+5, 0,0, number=True)

            if not catan.game.state.activePlayer.wants:
                cButton.hidden = True
                continue

            traderOffer = []
            for cls, howMany in catan.game.state.activePlayer.wants.items():
                if howMany:
                    traderOfferClass = cls
                    traderOffer = [cls()]
            if traderOffer:
                xoffset = x + classes.index(traderOfferClass)*8
                draw_cards(traderOffer, self.image,
                           xoffset, y+10, 0,0, number=True)

            proposal = [traderOffer, [card.__class__ for card in playerOffer]]

            # draw proposematch button
            mButton.hidden = False
            mButton.proposal = proposal
            mButton.x = x
            mButton.y = y+40
            mButton.update()
            self.image.blit(mButton.image, mButton.rect)

            # draw proposeconfirm button
            if self.matchesProposal(proposal):
                cButton.hidden = False
                cButton.proposal = proposal
                cButton.x = x
                cButton.y = y+52
                cButton.update()
                self.image.blit(cButton.image, cButton.rect)

    #----------------------------------------------------------------------
    def update(self):
        self.drawBg()
        self.drawCards()
        self.drawOpponents()
        self.drawMaritime()
        self.drawButtons()

        self.dirty = False

    #----------------------------------------------------------------------
    def onProposeTrade(self, player, toGive, toTake):
        self.dirty = True

    #----------------------------------------------------------------------
    def onConfirmProposal(self, *args):
        self.reset()

    #----------------------------------------------------------------------
    def onMaritimeTrade(self, *args):
        self.reset()

    #----------------------------------------------------------------------
    def onHideTrade(self):
        TradeDisplay.singleton_guard = False
        self.kill()
        events.unregisterListener(self)
        self.giveButtons = None
        self.takeButtons = None

    #----------------------------------------------------------------------
    def onMouseMotion(self, pos, buttons):
        if not self.rect.collidepoint(pos):
            return
        innerPos = vect_diff(pos, self.topleft)
        for button in (self.giveButtons.values()
                      + self.takeButtons.values()
                      + self.textButtons
                      + self.confirmButtons
                      + self.maritimeConfirmButtons
                      + self.maritimeMatchButtons
                      + self.matchButtons):
            if hasattr(button, 'onMouseMotion'):
                button.onMouseMotion(innerPos, buttons)

    #----------------------------------------------------------------------
    def onMouseLeftDown(self, pos):
        if not self.rect.collidepoint(pos):
            return
        self.dirty = True
        innerPos = vect_diff(pos, self.topleft)
        for button in (self.giveButtons.values()
                      + self.takeButtons.values()
                      + self.textButtons
                      + self.confirmButtons
                      + self.maritimeConfirmButtons
                      + self.maritimeMatchButtons
                      + self.matchButtons):
            if button.rect.collidepoint(innerPos):
                button.click()


