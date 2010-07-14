#! /usr/bin/env python

import pygame

import events
import catan
from pygame_utils import *

#------------------------------------------------------------------------------
class OpponentButton(EasySprite):
    def __init__(self, parent, pos, opponent):
        EasySprite.__init__(self)
        self.image = EasySurface( (80,80) )
        self.rect = self.image.get_rect()
        self.rect.topleft = pos

        self.opponent = opponent
        self.parent = parent
        self.drawBg()
        self.drawCards()

    #----------------------------------------------------------------------
    def drawBg(self):
        self.image.fill( (0,0,20) )
        r = self.rect.move(0,0)
        r.topleft = 0,0
        pygame.draw.rect(self.image, blue, r, 8)

        txtImg = font_render(str(self.opponent.identifier),
                             color=self.opponent.color)
        self.image.blit(txtImg, r.midtop)

    #----------------------------------------------------------------------
    def drawCards(self):
        cards = self.opponent.cards
        draw_cards(cards, self.image, 2, 2, 3, 3)

    #----------------------------------------------------------------------
    def update(self):
        if not self.dirty:
            return
        self.drawBg()
        self.drawCards()
        self.dirty = False

    #----------------------------------------------------------------------
    def click(self):
        self.parent.chooseVictim(self.opponent)
        


#------------------------------------------------------------------------------
class ChooseVictimDisplay(EasySprite):
    singleton_guard = False
    def __init__(self, player, opponents):
        assert ChooseVictimDisplay.singleton_guard == False, 'TODO: make this safely ignored, not blow up.'
        EasySprite.__init__(self)
        events.registerListener(self)
        self.image = EasySurface( (280,180) )
        self.rect = self.image.get_rect()

        self.player = player
        self.opponents = opponents

        self.oButtons = {}

        self.drawBg()
        self.drawButtons()

        self.dirty = True

    #----------------------------------------------------------------------
    def drawBg(self):
        self.image.fill( (0,0,20) )
        r = self.rect.move(0,0)
        r.topleft = 0,0
        pygame.draw.rect(self.image, blue, r, 8)

        pygame.draw.rect(self.image, (200,200,255), r, 1)

    #----------------------------------------------------------------------
    def drawButtons(self):
        x = 10
        y = 20
        for opponent in self.opponents:
            self.oButtons[opponent] = OpponentButton(self, (x,y), opponent)
            self.image.blit(self.oButtons[opponent].image, (x,y))
            x += 80

    #----------------------------------------------------------------------
    def update(self):
        if not self.dirty:
            return
        self.drawBg()
        self.drawButtons()
        self.dirty = False

    #----------------------------------------------------------------------
    def chooseVictim(self, victim):
        events.post('RobRequest', self.player, victim)

    #----------------------------------------------------------------------
    def onRobRequest(self, player, victim):
        if player == self.player:
            events.unregisterListener(self)
            self.giveButtons = None
            self.removeButtons = None
            self.kill()

    #----------------------------------------------------------------------
    def onMouseLeftDown(self, pos):
        if not self.rect.collidepoint(pos):
            return
        self.dirty = True

        innerPos = vect_diff(pos, self.topleft)
        for opponent in self.opponents:
            button = self.oButtons[opponent]
            if button.rect.collidepoint(innerPos):
                button.click()
                break

