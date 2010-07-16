#! /usr/bin/env python

import itertools

import pygame
import pygame.sprite

import catan

red = (255,0,0)
green = (0,255,0)
blue = (0,0,255)
black = (0,0,0)
white = (255,255,255)

terrain_colors = {
    catan.Mountain: (100,100,100),
    catan.Mud:  (255,50,50),
    catan.Wheat:  (255,255,0),
    catan.Grass:  (100,255,100),
    catan.Forest:  (0,200,0),
    catan.Desert:  (240,240,200),
}

card_colors = {
    catan.Stone: terrain_colors[catan.Mountain],
    catan.Brick: terrain_colors[catan.Mud],
    catan.Grain: terrain_colors[catan.Wheat],
    catan.Sheep: terrain_colors[catan.Grass],
    catan.Wood:  terrain_colors[catan.Forest],
}

# -----------------------------------------------------------------------------
def vect_add(v1, v2):
    return v1[0]+v2[0], v1[1]+v2[1]
    
# -----------------------------------------------------------------------------
def vect_diff(v1, v2):
    return v1[0]-v2[0], v1[1]-v2[1]

# -----------------------------------------------------------------------------
def vect_mult(v1, v2):
    return v1[0]*v2[0], v1[1]*v2[1]

# -----------------------------------------------------------------------------
def vect_scal_mult(v1, s):
    return v1[0]*s, v1[1]*s

# -----------------------------------------------------------------------------
def font_render(text, size=20, color=(255,0,0)):
    font = pygame.font.Font(None, size)
    return font.render(text, 1, color)

# -----------------------------------------------------------------------------
def blit_at_center(img1, img2, rect1=None, rect2=None):
    if rect1 == None:
        rect1 = img1.get_rect()
    if rect2 == None:
        rect2 = img2.get_rect()
    pos = vect_diff(rect1.center, rect2.center)
    img1.blit(img2, pos)

# -----------------------------------------------------------------------------
def card_img(card):
    cardImg = pygame.Surface( (10,16) )
    cardImg.fill( card_colors[card.__class__] )
    pygame.draw.rect(cardImg, white, cardImg.get_rect(), 1)
    return cardImg

# -----------------------------------------------------------------------------
def draw_cards(cards, destImg, x, y, deltaX, deltaY, number=False):
    for i, card in enumerate(cards):
        cardImg = card_img(card)
        cardPos = vect_add((x,y), (deltaX*i,deltaY*i))
        destImg.blit(cardImg, cardPos)
    if cards and number:
        txtImg = font_render(str(i+1), color=black)
        destImg.blit(txtImg, vect_add(cardPos, (2,5)))
        txtImg = font_render(str(i+1), color=white)
        destImg.blit(txtImg, vect_add(cardPos, (1,3)))

# -----------------------------------------------------------------------------
def victoryCard_img(card):
    cardImg = pygame.Surface( (10,16) )
    cardImg.fill( white )
    pygame.draw.rect(cardImg, black,
                     cardImg.get_rect().inflate((-2,-2)), 1)
    txtImg = font_render(card.__class__.__name__[:2], size=9)
    blit_at_center(cardImg, txtImg)
    return cardImg

# -----------------------------------------------------------------------------
def sort_cards(cards):
    def clsCmp(x,y):
        return cmp(x.__class__, y.__class__)
    return sorted(cards, cmp=clsCmp)

# -----------------------------------------------------------------------------
def group_cards(cards, asDict=False):
    def clsKeyfn(x):
        return x.__class__
    result = itertools.groupby(sort_cards(cards), clsKeyfn)
    if asDict:
        d = {}
        for cls, grouper in result:
            d[cls] = list(grouper)
        result = d
    return result


# -----------------------------------------------------------------------------
class Highlightable(object):
    def __init__(self):
        self.dirty = True
        self._hintlighted = False
        self._hoverlighted = False

    #----------------------------------------------------------------------
    def getHintlight(self):
        return self._hintlighted
    def setHintlight(self, value):
        self._hintlighted = value
        self.dirty = True
    hintlighted = property(getHintlight, setHintlight)

    #----------------------------------------------------------------------
    def getHoverlight(self):
        return self._hoverlighted
    def setHoverlight(self, value):
        self._hoverlighted = value
        self.dirty = True
    hoverlighted = property(getHoverlight, setHoverlight)

    #----------------------------------------------------------------------
    def checkHover(self, pos):
        if self.rect.collidepoint(pos):
            self.hoverlighted = True
        elif self.hoverlighted:
            self.hoverlighted = False

    #----------------------------------------------------------------------
    def onRefreshState(self):
        self.dirty = True


# -----------------------------------------------------------------------------
class EasySurface(pygame.Surface):
    def __init__(self, sizeSpec):
        if isinstance(sizeSpec, pygame.Rect):
            sizeSpec = sizeSpec.size
        pygame.Surface.__init__(self, sizeSpec, flags=pygame.SRCALPHA)


# -----------------------------------------------------------------------------
class EasySprite(pygame.sprite.Sprite):
    def __init__(self, *args):
        pygame.sprite.Sprite.__init__(self, *args)

    #----------------------------------------------------------------------
    def __getattr__(self, attrname):
        try:
            return pygame.sprite.Sprite.__getattribute__(self, attrname)
        except AttributeError:
            if ('rect' in self.__dict__
               and hasattr(self.__dict__['rect'], attrname)):
                return getattr(self.__dict__['rect'], attrname)
            raise

    #----------------------------------------------------------------------
    def __setattr__(self, attrname, val):
        l = ('x y width height center centerx centery topleft midtop topright'
             ' right bottomright midbottom bottomleft left').split()
        if attrname in l:
            return setattr(self.__dict__['rect'], attrname, val)
        return pygame.sprite.Sprite.__setattr__(self, attrname, val)


#------------------------------------------------------------------------------
class SimpleTextButton(EasySprite, Highlightable):
    def __init__(self, size, text):
        EasySprite.__init__(self)
        Highlightable.__init__(self)
        self.text = text
        self.rect = pygame.Rect(0,0, *size)
        self.image = EasySurface(self.rect.size)
        self.draw()

    #----------------------------------------------------------------------
    def update(self):
        if not self.dirty:
            return
        self.draw()

    #----------------------------------------------------------------------
    def draw(self):
        self.image.fill(black)
        r = self.rect.move(-self.x, -self.y)
        pygame.draw.rect(self.image, blue, r, 2)

        if self.hoverlighted:
            color = white
        elif self.hintlighted:
            color = (255,100,100)
        else:
            color = red
        txtImg = font_render(self.text, color=color)
        blit_at_center(self.image, txtImg)

        self.dirty = False

    #----------------------------------------------------------------------
    def onMouseMotion(self, pos, buttons):
        self.checkHover(pos)


#------------------------------------------------------------------------------
class CardAddButton(EasySprite):
    def __init__(self, parent, pos, cardClass, symbol='+'):
        EasySprite.__init__(self)
        self.image = font_render(symbol, size=50)
        self.rect = self.image.get_rect()
        self.rect.topleft = pos

        self.cardClass = cardClass
        self.parent = parent

    #----------------------------------------------------------------------
    def cardSubset(self):
        return set([card for card in self.parent.player.cards
                    if isinstance(card, self.cardClass)])

#------------------------------------------------------------------------------
class CardRemoveButton(CardAddButton):
    def __init__(self, parent, pos, cardClass):
        CardAddButton.__init__(self, parent, pos, cardClass, symbol='-')

