#! /usr/bin/env python

import pygame

import events
import catan
from pygame_utils import *

#------------------------------------------------------------------------------
class ChooseAddButton(CardAddButton):
    #def __init__(self, parent, pos, cardClass, symbol='+'):
    def click(self):
        self.parent.addChoose(self.cardClass)

#------------------------------------------------------------------------------
class ChooseRemoveButton(CardRemoveButton):
    def click(self):
        self.parent.removeChoose(self.cardClass)

#------------------------------------------------------------------------------
class ChooseTextButton(SimpleTextButton):
    def __init__(self, pos):
        SimpleTextButton.__init__(self, (70,15), 'CHOOSE')
        self.rect.topleft = pos

#------------------------------------------------------------------------------
class ChooseTwoCardsDisplay(EasySprite):
    singleton_guard = False
    def __init__(self, player):
        assert ChooseTwoCardsDisplay.singleton_guard == False
        ChooseTwoCardsDisplay.singleton_guard = True
        EasySprite.__init__(self)
        events.registerListener(self)
        self.image = EasySurface( (280,80) )
        self.rect = self.image.get_rect()

        self.player = player

        self._chosen = []

        self.addButtons = {}
        self.removeButtons = {}

        self.drawBg()
        self.drawCards()

        self.dButton = ChooseTextButton((200,60))
        self.drawButtons()

        self.dirty = True

    #----------------------------------------------------------------------
    def addChoose(self, cardClass):
        if len(self._chosen) < 2:
            self._chosen.append(cardClass)
            self.dirty = True

    #----------------------------------------------------------------------
    def removeChoose(self, cardClass):
        if cardClass in self._chosen:
            self._chosen.remove(cardClass)
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
            self.addButtons[cls] = ChooseAddButton(self, addPos, cls)

            removePos = vect_add((x,y), (0, 30))
            self.removeButtons[cls] = ChooseRemoveButton(self, removePos, cls)

            group = [cls()]
            draw_cards(group, self.image, x, y, 2, 3)

            x += 30

        if self._chosen:
            x = 210
            y = 40
            group = [cardClass() for cardClass in self._chosen]
            draw_cards(group, self.image, x, y, 6, 0)
           

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

        if len(self._chosen) == 2:
            self.dButton.hintlighted = True
        else:
            self.dButton.hintlighted = False

        self.drawBg()
        self.drawCards()
        self.drawButtons()
        self.dirty = False

    #----------------------------------------------------------------------
    def onChooseTwoCards(self, player, cards):
        if player == self.player:
            ChooseTwoCardsDisplay.singleton_guard = False
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
                #print 'button %s sees mouse inner' % button
                button.click()
        if self.dButton.rect.collidepoint(innerPos):
            if self.dButton.hintlighted:
                events.post('ChooseTwoCardsRequest', self.player, self._chosen)

