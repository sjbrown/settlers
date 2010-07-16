#! /usr/bin/env python


import pygame

import events
import catan
from pygame_utils import *

#------------------------------------------------------------------------------
class MonopolyAddButton(CardAddButton):
    def click(self):
        self.parent.addMonopoly(self.cardClass)

#------------------------------------------------------------------------------
class MonopolyTextButton(SimpleTextButton):
    def __init__(self, pos):
        SimpleTextButton.__init__(self, (80,15), 'MONOPOLIZE')
        self.rect.topleft = pos

#------------------------------------------------------------------------------
class MonopolyDisplay(EasySprite):
    def __init__(self, player):
        EasySprite.__init__(self)
        events.registerListener(self)
        self.image = EasySurface( (280,80) )
        self.rect = self.image.get_rect()

        self.player = player

        self._chosen = None

        self.addButtons = {}

        self.drawBg()
        self.drawCards()

        self.dButton = MonopolyTextButton((200,60))
        self.drawButtons()

        self.dirty = True

    #----------------------------------------------------------------------
    def addMonopoly(self, cardClass):
        self._chosen = cardClass
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
            self.addButtons[cls] = MonopolyAddButton(self, addPos, cls)

            group = [cls()]
            draw_cards(group, self.image, x, y, 2, 3)

            x += 30

        if self._chosen:
            x = 210
            y = 40
            group = [self._chosen()]
            draw_cards(group, self.image, x, y, 6, 0)
           

    #----------------------------------------------------------------------
    def drawButtons(self):
        self.dButton.update()
        self.image.blit(self.dButton.image, self.dButton.rect)
        for button in self.addButtons.values():
            self.image.blit(button.image, button.rect)

    #----------------------------------------------------------------------
    def update(self):
        if not self.dirty:
            return

        if self._chosen:
            self.dButton.hintlighted = True
        else:
            self.dButton.hintlighted = False

        self.drawBg()
        self.drawCards()
        self.drawButtons()
        self.dirty = False

    #----------------------------------------------------------------------
    def onMonopoly(self, player, cardClass):
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
        for button in self.addButtons.values():
            if button.rect.collidepoint(innerPos):
                button.click()
        if self.dButton.rect.collidepoint(innerPos):
            if self.dButton.hintlighted:
                events.post('MonopolyRequest', self.player, self._chosen)
            

