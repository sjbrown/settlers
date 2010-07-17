#! /usr/bin/env python


import pygame

import events
import catan
from pygame_utils import *


#------------------------------------------------------------------------------
class DiscardAddButton(CardAddButton):
    def click(self):
        group = self.cardSubset()
        undiscarded = group.difference(set(self.parent._discards))
        if undiscarded:
            self.parent.addDiscard(undiscarded.pop())

#------------------------------------------------------------------------------
class DiscardRemoveButton(CardRemoveButton):
    def click(self):
        group = self.cardSubset()
        discarded = group.intersection(set(self.parent._discards))
        if discarded:
            self.parent.removeDiscard(discarded.pop())

#------------------------------------------------------------------------------
class DiscardTextButton(SimpleTextButton):
    def __init__(self, pos):
        SimpleTextButton.__init__(self, (70,15), 'DISCARD')
        self.rect.topleft = pos

#------------------------------------------------------------------------------
class DiscardDisplay(EasySprite):
    def __init__(self, player):
        EasySprite.__init__(self)
        events.registerListener(self)
        self.image = EasySurface( (280,80) )
        self.rect = self.image.get_rect()

        self.player = player

        self._discards = []

        self.addButtons = {}
        self.removeButtons = {}

        self.drawBg()
        self.drawCards()

        self.dButton = DiscardTextButton((200,60))
        self.drawButtons()

        self.dirty = True

    #----------------------------------------------------------------------
    def addDiscard(self, card):
        self._discards.append(card)
        self.dirty = True

    #----------------------------------------------------------------------
    def removeDiscard(self, card):
        self._discards.remove(card)
        self.dirty = True

    #----------------------------------------------------------------------
    def drawBg(self):
        self.image.fill( (0,0,20) )
        r = self.rect.move(0,0)
        r.topleft = 0,0
        pygame.draw.rect(self.image, blue, r, 8)

        pygame.draw.rect(self.image, (200,200,255), r, 1)

    #----------------------------------------------------------------------
    def drawCards(self):
        classes = [catan.Stone, catan.Brick, catan.Grain, catan.Sheep,
                   catan.Wood]
        x = 10
        y = 20
        for cls in classes:
            addPos = vect_add((x,y), (0, -25))
            self.addButtons[cls] = DiscardAddButton(self, addPos, cls)

            removePos = vect_add((x,y), (0, 30))
            self.removeButtons[cls] = DiscardRemoveButton(self, removePos, cls)

            group = [card for card in self.player.cards
                     if isinstance(card, cls)]

            draw_cards(group, self.image, x, y, 2, 3)
            x += 30

        if self._discards:
            #self.dButton = ChooseTextButton((200,60))
            x = 210
            y = 40
            draw_cards(self._discards, self.image, x, y, 6, 0)

    #----------------------------------------------------------------------
    def drawButtons(self):
        self.dButton.update()
        self.image.blit(self.dButton.image, self.dButton.rect)
        for button in self.addButtons.values():
            self.image.blit(button.image, button.rect)
        for button in self.removeButtons.values():
            self.image.blit(button.image, button.rect)

    #----------------------------------------------------------------------
    def update(self):
        if not self.dirty:
            return

        if len(self._discards) == len(self.player.cards)//2:
            self.dButton.hintlighted = True
        else:
            self.dButton.hintlighted = False

        self.drawBg()
        self.drawCards()
        self.drawButtons()
        self.dirty = False

    #----------------------------------------------------------------------
    def onDiscard(self, player):
        if player == self.player:
            events.unregisterListener(self)
            self.addButtons = None
            self.removeButtons = None
            self.kill()

    #----------------------------------------------------------------------
    def onMouseLeftDown(self, pos):
        if not self.rect.collidepoint(pos):
            return
        self.dirty = True
        innerPos = vect_diff(pos, self.topleft)
        for button in self.addButtons.values() + self.removeButtons.values():
            #print 'button', button, button.rect
            if button.rect.collidepoint(innerPos):
                print 'button %s sees mouse inner' % button
                button.click()
        if self.dButton.rect.collidepoint(innerPos):
            if self.dButton.hintlighted:
                events.post('DiscardRequest', self.player, self._discards)

