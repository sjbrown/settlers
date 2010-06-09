#! /usr/bin/env python

import sys
import time
import string
import itertools

from collections import defaultdict

import pygame
import pygame.sprite
from pygame.locals import * #the KeyboardController needs these

import events
import catan
import mapmodel
import textrect
from mapmodel import walk_corners_along_tile

tileGroup = pygame.sprite.RenderUpdates()
tileModelToSprite = {}
cornerGroup = pygame.sprite.RenderUpdates()
cornerModelToSprite = {}
edgeGroup = pygame.sprite.RenderUpdates()
edgeModelToSprite = {}
hudGroup = pygame.sprite.RenderUpdates()

terrain_colors = {
    catan.Mountain: (100,100,100) ,
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

red = (255,0,0)
green = (0,255,0)
blue = (0,0,255)
black = (0,0,0)
white = (255,255,255)

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
def drawVictoryCard(card):
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

    def getHintlight(self):
        return self._hintlighted
    def setHintlight(self, value):
        self._hintlighted = value
        self.dirty = True
    hintlighted = property(getHintlight, setHintlight)

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

    def __getattr__(self, attrname):
        try:
            return pygame.sprite.Sprite.__getattribute__(self, attrname)
        except AttributeError:
            if ('rect' in self.__dict__
               and hasattr(self.__dict__['rect'], attrname)):
                return getattr(self.__dict__['rect'], attrname)
            raise

    def __setattr__(self, attrname, val):
        l = ('x y width height center centerx centery topleft midtop topright'
             ' right bottomright midbottom bottomleft left').split()
        if attrname in l:
            return setattr(self.__dict__['rect'], attrname, val)
        return pygame.sprite.Sprite.__setattr__(self, attrname, val)

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



#------------------------------------------------------------------------------
class CPUSpinnerController:
    def __init__(self):
        events.registerListener( self )
        self.keepGoing = 1

    def run(self):
        while self.keepGoing:
            events.post(events.Tick())

    def onQuit(self):
        #this will stop the while loop from running
        self.keepGoing = False

#------------------------------------------------------------------------------
class KeyboardController:
    """KeyboardController takes Pygame events generated by the
    keyboard and uses them to control the model, by sending Requests
    or to control the Pygame display directly, as with the QuitEvent
    """
    def __init__(self, playerName=None):
        '''playerName is an optional argument; when given, this
        keyboardController will control only the specified player
        '''
        events.registerListener( self )

        self.activePlayer = None
        self.playerName = playerName
        self.players = []

    def onTick(self):
        #Handle Input Events
        for event in pygame.event.get():
            ev = None
            if event.type == QUIT:
                ev = events.Quit()
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    # Hit Shift-ESC or Ctrl-ESC to go to the debugger
                    # otherwise ESC will quit the game
                    if event.mod:
                        import pdb
                        pdb.set_trace()
                    else:
                        ev = events.Quit()
                else:
                    ev = ('KeyDown', event.key, event.unicode, event.mod)
            elif event.type == MOUSEBUTTONDOWN:
                if event.button == 1:
                    events.post('MouseLeftDown', pos=event.pos)
            elif event.type == MOUSEBUTTONUP:
                if event.button == 1:
                    events.post('MouseLeftUp', pos=event.pos)
            elif event.type == MOUSEMOTION:
                events.post('MouseMotion', pos=event.pos, buttons=event.buttons)
            if ev:
                if isinstance(ev, tuple):
                    events.post( *ev )
                else:
                    events.post( ev )

#------------------------------------------------------------------------------
class TextButton(EasySprite, Highlightable):
    def __init__(self, size, text):
        EasySprite.__init__(self)
        Highlightable.__init__(self)
        events.registerListener(self)
        hudGroup.add(self)
        self.text = text
        self.rect = Rect(0,0, *size)
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
class EndTurnButton(TextButton):
    def __init__(self):
        TextButton.__init__(self, (150,50), 'END TURN')

    #----------------------------------------------------------------------
    def onMouseLeftDown(self, pos):
        if self.rect.collidepoint(pos):
            events.post('TurnFinishRequest', humanPlayer)


#------------------------------------------------------------------------------
class TradeButton(TextButton):
    def __init__(self):
        TextButton.__init__(self, (150,50), 'TRADE')

    #----------------------------------------------------------------------
    def onMouseLeftDown(self, pos):
        if self.rect.collidepoint(pos):
            if catan.game.state.stage != catan.Stages.playerTurn:
                print "Can only trade during active player's turn"
                return
            events.post('ShowTrade')


#------------------------------------------------------------------------------
class SaveGameButton(TextButton):
    def __init__(self):
        TextButton.__init__(self, (150,50), 'SAVE GAME')

    #----------------------------------------------------------------------
    def onMouseLeftDown(self, pos):
        if self.rect.collidepoint(pos):
            print '        SAVED   **************'
            import saved_game
            saved_game.save()


#------------------------------------------------------------------------------
class Console(EasySprite):
    def __init__(self):
        EasySprite.__init__(self)
        events.registerListener(self)
        self.image = EasySurface( (300,80) )
        self.rect = self.image.get_rect()

        self.outText = dict(text='...console output...', color=green )
        self.inText = dict(text='|', color=green )

        self.drawBg()
        self.drawText()

        hudGroup.add(self)
        self.dirty = True

    #----------------------------------------------------------------------
    def drawBg(self):
        bg = self.image.copy()
        r = self.rect.move(0,0)
        r.topleft = 0,0
        pygame.draw.rect(bg, green, r, 2)

        r.y = r.height/2
        r.height = r.height/2
        pygame.draw.rect(bg, green, r, 1)

        self.image.blit(bg, (0,0))

    #----------------------------------------------------------------------
    def drawText(self):
        r = self.rect.move(0,0)
        r.topleft = 0,0
        halfY = r.height/2
        #r.topleft = 2,2
        r.height = halfY
        r.inflate_ip(-4,-4)
        #print 'rendering', self.outText, 'on', r
        txtImg = textrect.render_textrect(rect=r,**self.outText)
        self.image.blit(txtImg, r)

        r.y = halfY + 2
        txtImg = font_render(**self.inText)
        self.image.blit(txtImg, r)

    #----------------------------------------------------------------------
    def update(self):
        self.image.fill(black)
        self.drawBg()
        self.drawText()

    #----------------------------------------------------------------------
    def onKeyDown(self, keycode, keyletter, mods):
        if keycode == K_BACKSPACE:
            self.inText['text'] = self.inText['text'][:-2] +'|'
        elif keycode == K_RETURN:
            statement = self.inText['text'][:-1]
            self.inText['text'] = '|'
            try:
                exec statement
            except Exception, ex:
                out = str(ex)
                self.outText['text'] = out
        elif keyletter in string.printable:
            self.inText['text'] = self.inText['text'][:-1] + keyletter +'|'
        
    #----------------------------------------------------------------------
    def notify(self, event):
        if isinstance(event, events.Tick):
            return
        text = self.outText['text']
        lines = text.split('\n')
        self.outText['text'] = '\n'.join([lines[-1], str(event)]) #last 2 items

#------------------------------------------------------------------------------
class DiceButton(EasySprite, Highlightable):
    def __init__(self):
        EasySprite.__init__(self)
        Highlightable.__init__(self)
        events.registerListener(self)
        self.image = EasySurface( (150,100) )
        self.rect = self.image.get_rect()

        self.diceText1 = dict(text='*', size=30, color=(255,0,0) )
        self.diceText2 = dict(text='*', size=30, color=(255,0,0) )

        self.drawBg()
        self.drawText()

        hudGroup.add(self)

    #----------------------------------------------------------------------
    def drawBg(self):
        bg = EasySurface( (150,100) )
        r = self.rect.move(0,0)
        r.topleft = 0,0
        pygame.draw.rect(bg, blue, r, 2)
        r.size = 60,60
        r.topleft = 8,8
        pygame.draw.rect(bg, blue, r, 1)
        r.topright = 142,8
        pygame.draw.rect(bg, blue, r, 1)
        self.image.blit(bg, (0,0))

    #----------------------------------------------------------------------
    def drawText(self):
        r = self.rect.move(0,0)

        if self.hoverlighted:
            color = white
        elif self.hintlighted:
            color = (255,100,100)
        else:
            color = red
        r.topleft = 0,35
        txtImg = font_render('ROLL', color=color)
        blit_at_center(self.image, txtImg, rect1=r)

        r.size = 50,50
        r.topleft = 12,12
        txtImg = font_render(**self.diceText1)
        self.image.blit(txtImg, r)

        r.topleft = 92,12
        txtImg = font_render(**self.diceText2)
        self.image.blit(txtImg, r)

    #----------------------------------------------------------------------
    def update(self):
        if catan.game.state.stage == catan.Stages.preRoll:
            self.hintlighted = True
        else:
            self.hintlighted = False
        self.image.fill(black)
        self.drawBg()
        self.drawText()
        self.dirty = False

    #----------------------------------------------------------------------
    def onDiceRoll(self, d1, d2):
        self.diceText1['text'] = str(d1)
        self.diceText2['text'] = str(d2)

    #----------------------------------------------------------------------
    def onMouseMotion(self, pos, buttons):
        self.checkHover(pos)

    #----------------------------------------------------------------------
    def onMouseLeftDown(self, pos):
        if self.rect.collidepoint(pos):
            events.post('DiceRollRequest', humanPlayer)

#------------------------------------------------------------------------------
class UseCardButton(EasySprite, Highlightable):
    def __init__(self, victoryCardClass):
        EasySprite.__init__(self)
        Highlightable.__init__(self)
        events.registerListener(self)
        self.image = EasySurface( (50,50) )
        self.rect = self.image.get_rect()
        hudGroup.add(self)

        self.victoryCardClass = victoryCardClass

        self.draw()

    #----------------------------------------------------------------------
    def update(self):
        if not self.dirty:
            return
        self.calculateHintlight()
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
        txt = self.victoryCardClass.__name__[0]
        txtImg = font_render(txt, color=color, size=30)
        blit_at_center(self.image, txtImg)

        if humanPlayer:
            card = humanPlayer.getVictoryCardOfClass(self.victoryCardClass)
            if card:
                cardImg = drawVictoryCard(card)
                self.image.blit(cardImg, (5,10))

        self.dirty = False

    #----------------------------------------------------------------------
    def onMouseMotion(self, pos, buttons):
        self.checkHover(pos)

    #----------------------------------------------------------------------
    def onMouseLeftDown(self, pos):
        if self.rect.collidepoint(pos):
            events.post('PlayVictoryCardRequest', humanPlayer,
                        self.victoryCardClass)

    #----------------------------------------------------------------------
    def onStageChange(self, *args):
        self.dirty = True

    #----------------------------------------------------------------------
    def calculateHintlight(self):
        if (catan.game.state.stage in (catan.Stages.preRoll,
                                      catan.Stages.playerTurn)
            and humanPlayer.getVictoryCardOfClass(self.victoryCardClass)):
            self.hintlighted = True
        else:
            self.hintlighted = False

#------------------------------------------------------------------------------
class SoldierButton(UseCardButton):
    def __init__(self):
        UseCardButton.__init__(self, catan.Soldier)

#------------------------------------------------------------------------------
class YearOfPlentyButton(UseCardButton):
    def __init__(self):
        UseCardButton.__init__(self, catan.YearOfPlenty)

    #----------------------------------------------------------------------
    def onChooseTwoCards(self, *args):
        self.dirty = True

#------------------------------------------------------------------------------
class MonopolyButton(UseCardButton):
    def __init__(self):
        UseCardButton.__init__(self, catan.Monopoly)

    #----------------------------------------------------------------------
    def onMonopoly(self, *args):
        self.dirty = True


#------------------------------------------------------------------------------
class BuyButton(EasySprite, Highlightable):
    def __init__(self, itemClass, text):
        EasySprite.__init__(self)
        Highlightable.__init__(self)
        events.registerListener(self)
        self.image = EasySurface( (50,50) )
        self.rect = self.image.get_rect()
        hudGroup.add(self)

        self.text = text

        self.itemClass = itemClass

        self.draw()

    #----------------------------------------------------------------------
    def update(self):
        if not self.dirty:
            return
        self.calculateHintlight()
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
        txtImg = font_render(self.text, color=color, size=30)
        blit_at_center(self.image, txtImg)

        self.dirty = False

    #----------------------------------------------------------------------
    def onMouseMotion(self, pos, buttons):
        self.checkHover(pos)

    #----------------------------------------------------------------------
    def onMouseLeftDown(self, pos):
        if self.rect.collidepoint(pos):
            events.post('BuyRequest', humanPlayer, self.itemClass)

    #----------------------------------------------------------------------
    def calculateHintlight(self):
        item = self.itemClass()
        if not humanPlayer.neededCardClasses(item):
            self.hintlighted = True
        else:
            self.hintlighted = False

    #----------------------------------------------------------------------
    def onRob(self, thief, victim, card):
        if humanPlayer in [thief, victim]:
            self.dirty = True

    #----------------------------------------------------------------------
    def onDiscard(self, player):
        if player == humanPlayer:
            self.dirty = True
        
    #----------------------------------------------------------------------
    def onHarvest(self, cards, sourceTile, recipient):
        if recipient == humanPlayer:
            self.dirty = True

    #----------------------------------------------------------------------
    def onPlayerPlacing(self, *args):
        self.dirty = True

    #----------------------------------------------------------------------
    def onPlayerDrewVictoryCard(self, *args):
        self.dirty = True


#------------------------------------------------------------------------------
class BuySettlementButton(BuyButton):
    def __init__(self):
        BuyButton.__init__(self, catan.Settlement, 'S')

#------------------------------------------------------------------------------
class BuyRoadButton(BuyButton):
    def __init__(self):
        BuyButton.__init__(self, catan.Road, 'R')

#------------------------------------------------------------------------------
class BuyCityButton(BuyButton):
    def __init__(self):
        BuyButton.__init__(self, catan.City, 'C')

#------------------------------------------------------------------------------
class BuyVictoryCardButton(BuyButton):
    def __init__(self):
        BuyButton.__init__(self, catan.VictoryCard, 'V')

#------------------------------------------------------------------------------
class ItemSprite(EasySprite):
    def __init__(self, itemLetter, thing):
        self.thing = thing
        self.image = font_render(itemLetter, color=thing.owner.color)

#------------------------------------------------------------------------------
class SettlementSprite(ItemSprite):
    def __init__(self, settlement):
        ItemSprite.__init__(self, 'S', settlement)

#------------------------------------------------------------------------------
class CitySprite(ItemSprite):
    def __init__(self, city):
        ItemSprite.__init__(self, 'C', city)

#------------------------------------------------------------------------------
class RoadSprite(ItemSprite):
    def __init__(self, road):
        ItemSprite.__init__(self, 'R', road)


#------------------------------------------------------------------------------
class Tile(EasySprite, Highlightable):
    def __init__(self, tile):
        EasySprite.__init__(self)
        Highlightable.__init__(self)
        events.registerListener(self)

        self.image = EasySurface( (100,100) )
        self.rect = self.image.get_rect()
        r = self.rect

        #self.image.fill( (0,255,128) )
        text = tile.name
        textImg = font_render(text)
        self.image.blit( textImg, r.center )

        self.tile = tile
        self.calcCornerPositions()

        tileGroup.add(self)
        tileModelToSprite[tile] = self

    def collides(self, point):
        if not self.rect.collidepoint(point):
            return False
        # TODO: make this return true when the point is inside the hexagon
        return True

    def calcCornerPositions(self):
        r = self.rect
        We = r.midleft
        NW = (r.width/3, r.top)
        NE = (2*r.width/3, r.top)
        Ea = r.midright
        SE = (2*r.width/3, r.bottom)
        SW = (r.width/3, r.bottom)
        if self.tile.name == 't01':
            self.cornerPositions = [ NW, We, NE, SW, Ea, SE ]
        elif self.tile.name in ['t02','t10']:
            self.cornerPositions = [ Ea, SE, NE, SW, NW, We ]
        elif self.tile.name in ['t03', 't12']:
            self.cornerPositions = [ SW, SE, We, Ea, NW, NE ]
        elif self.tile.name in ['t04', 't14']:
            self.cornerPositions = [ NE, Ea, NW, SE, We, SW ]
        elif self.tile.name in ['t05', 't16']:
            self.cornerPositions = [ We, SW, NW, SE, NE, Ea ]
        elif self.tile.name in ['t06', 't18']:
            self.cornerPositions = [ NW, NE, We, Ea, SW, SE ]
        elif self.tile.name in ['t07', 't17', 't19']:
            self.cornerPositions = [ NW, We, NE, SW, Ea, SE ]
        elif self.tile.name in ['t08']:
            self.cornerPositions = [ SE, SW, Ea, We, NE, NW ]
        elif self.tile.name in ['t09']:
            self.cornerPositions = [ Ea, NE, SE, NW, SW, We ]
        elif self.tile.name in ['t11']:
            self.cornerPositions = [ SW, We, SE, NW, Ea, NE ]
        elif self.tile.name in ['t13']:
            self.cornerPositions = [ NE, NW, Ea, We, SE, SW ]
        elif self.tile.name in ['t15']:
            self.cornerPositions = [ We, NW, SW, NE, SE, Ea ]
        else:
            raise Exception('unknown tile')

    def update(self):
        if not self.dirty:
            return

        r = self.rect.move((0,0))
        r.topleft = 0,0

        # draw the terrain color
        terrain = self.tile.terrain
        if terrain:
            color = terrain_colors[terrain.__class__]
            pygame.draw.circle(self.image, color, r.center, r.width/2)
            if self.hintlighted:
                color2 = [float(x)/280*255 for x in color]
                radius2 = r.width/2 - 10
                pygame.draw.circle(self.image, color2, r.center, radius2)

        # draw the tile name
        text = self.tile.name
        textImg = font_render(text, color=(0,0,0, 18))
        self.image.blit(textImg, vect_add(r.midtop,(0,20)))

        # draw the pip
        if self.tile.pip:
            size = 30 - 2*abs(7 - self.tile.pip.value)
            textImg = font_render(str(self.tile.pip.value), size=size)
            blit_at_center(self.image, textImg)

        # draw the robber
        if self.tile.robber:
            textImg = font_render('X', color=black, size=36)
            blit_at_center(self.image, textImg)

        #self.debug_draw()

        self.dirty = False

    def debug_draw(self):
        for i, c in enumerate(self.tile.corners):
            corner = cornerModelToSprite[c]
            r = corner.rect.move((0,0))
            r.center = self.cornerPositions[i]
            r.clamp_ip(self.image.get_rect())
            self.image.blit(corner.image, r.topleft)
        for i, e in enumerate(self.tile.edges):
            text = e.name
            textImg = font_render(text, size=15, color=blue)
            if len(e.corners) == 2:
                c1, c2 = e.corners
                corner = cornerModelToSprite[c1]
                pos1 = corner.rect.center
                corner = cornerModelToSprite[c2]
                pos2 = corner.rect.center
                pygame.draw.aaline(self.image, blue, pos1, pos2)
                r = pygame.Rect(pos1[0], pos1[1],
                                (pos2[0] - pos1[0]), (pos2[1] - pos1[1]))
                self.image.blit(textImg, r.center)
            else:
                self.image.blit(textImg, (40,14*i))

    def onHintLightTiles(self, tiles):
        if self.tile in tiles:
            self.hintlighted = True

    def onRobberPlaced(self, *args):
        self.hintlighted = False

    def onMouseLeftDown(self, pos):
        if self.hintlighted and self.collides(pos):
            # TODO: there is a bug here.
            # If the user interface sends two TileClicked events immediately
            # after another (such as if the user clicks on an overlap), the
            # event manager will get two of these and place the robber twice
            # consider making a special queue for UI events like clicks
            events.post('TileClicked', self.tile)
                

#------------------------------------------------------------------------------
class Corner(EasySprite, Highlightable):
    def __init__(self, corner):
        #print 'making corner', corner.name
        EasySprite.__init__(self)
        Highlightable.__init__(self)
        events.registerListener(self)

        self.image = EasySurface( (22,22) )
        self.rect = self.image.get_rect()
        self.corner = corner

        self.drawBg()

        cornerGroup.add(self)
        cornerModelToSprite[corner] = self


    def drawBg(self):
        if self.hoverlighted:
            bgcolor = (0,255,28, 250)
        elif self.hintlighted:
            bgcolor = (0,255,28, 200)
        else:
            bgcolor = (0,255,28, 128)
        self.image.fill( bgcolor )
        text = self.corner.name
        textImg = font_render(text, size=15, color=(5,0,0))
        self.image.blit( textImg, (0,0) )
        if self.hintlighted:
            pygame.draw.rect(self.image, white, self.image.get_rect(), 1)

    def update(self):
        if not self.dirty:
            return

        for e in self.corner.edges:
            eSprite = edgeModelToSprite.get(e)
            if eSprite:
                eSprite.dirty = True

        self.drawBg()

        if self.corner.stuff:
            thing = self.corner.stuff[0]
            if isinstance(thing, catan.Settlement):
                txtImg = SettlementSprite(thing).image
            if isinstance(thing, catan.City):
                txtImg = CitySprite(thing).image
            self.image.blit( txtImg, (8,8) )

        self.move_to_absolute_position()
        self.dirty = False

    def move_to_absolute_position(self):
        corner = self.corner
        tile = corner.tiles[0]
        idx = tile.corners.index(self.corner)
        tSprite = tileModelToSprite[tile]
        rel_pos = tSprite.cornerPositions[idx]
        abs_pos = vect_add(tSprite.topleft, rel_pos)
        self.topleft = (abs_pos)

    def onItemPlaced(self, item):
        if self.hoverlighted:
            self.hoverlighted = False
        if self.hintlighted:
            self.hintlighted = False
        if item.location == self.corner:
            self.dirty = True

    def onRobberPlaced(self, *args):
        self.dirty = True

    def onHintLightCorners(self, corners):
        if self.corner in corners:
            self.hintlighted = True

    def onMouseMotion(self, pos, buttons):
        if self.hintlighted:
            if self.rect.collidepoint(pos):
                self.hoverlighted = True
            else:
                self.hoverlighted = False
        
    def onMouseLeftDown(self, pos):
        if self.hoverlighted:
            if self.rect.collidepoint(pos):
                events.post('ClickCorner', self.corner)

                
#------------------------------------------------------------------------------
class Edge(EasySprite, Highlightable):
    def __init__(self, edge):
        #print 'making edge', edge.name
        EasySprite.__init__(self)
        Highlightable.__init__(self)
        events.registerListener(self)

        self.edge = edge

        edgeGroup.add(self)
        edgeModelToSprite[edge] = self

        if len(self.edge.corners) != 2:
            print '??'
            return

        c1, c2 = self.edge.corners
        cSprite = cornerModelToSprite[c1]
        r1 = cSprite.rect
        r1_point = pygame.Rect(r1.center,(1,1))
        cSprite = cornerModelToSprite[c2]
        r2 = cSprite.rect
        r2_point = pygame.Rect(r2.center,(1,1))

        self.rect = r1.union(r2)

        norm_rect = self.rect.move(0,0)
        norm_rect.normalize()
        self.image = EasySurface(self.rect)
        self.image.fill(blue)

    def update(self):
        if not self.dirty:
            return

        c1, c2 = self.edge.corners

        c1Sprite = cornerModelToSprite[c1]
        r1 = c1Sprite.rect
        r1_point = pygame.Rect(r1.center,(1,1))

        c2Sprite = cornerModelToSprite[c2]
        r2 = c2Sprite.rect
        r2_point = pygame.Rect(r2.center,(1,1))

        self.rect = r1.union(r2)

        norm_rect = self.rect.move(0,0)
        norm_rect.normalize()
        self.image = EasySurface(self.rect)

        if self.hoverlighted:
            color = (100,100,255, 255)
        elif self.hintlighted:
            color = (0,0,255, 255)
        else:
            color = (0,0,200, 255)

        #print 'drawing edge from, to', c1Sprite.center, c2Sprite.center
        point1 = vect_diff(c1Sprite.center, self.rect.topleft)
        point2 = vect_diff(c2Sprite.center, self.rect.topleft)
        pygame.draw.aaline(self.image, color, point1, point2)
        if self.hintlighted or self.hoverlighted:
            pygame.draw.circle(self.image, white, point1, 3)
            pygame.draw.circle(self.image, white, point2, 3)

        if self.edge.stuff:
            item = self.edge.stuff[0]
            txtImg = RoadSprite(item).image
            self.image.blit( txtImg, vect_diff(self.rect.center, self.rect.topleft))

        self.dirty = False

    def onItemPlaced(self, item):
        if self.hintlighted or self.hoverlighted:
            self.hintlighted = False
            self.hoverlighted = False
        if item.location == self.edge:
            self.dirty = True

    def onHintLightEdges(self, edges):
        if self.edge in edges:
            self.hintlighted = True

    def onRobberPlaced(self, *args):
        self.dirty = True

    def onMouseMotion(self, pos, buttons):
        if self.hintlighted:
            if self.rect.collidepoint(pos):
                self.hoverlighted = True
            else:
                self.hoverlighted = False
        
    def onMouseLeftDown(self, pos):
        if self.hoverlighted:
            if self.rect.collidepoint(pos):
                events.post('ClickEdge', self.edge)

#------------------------------------------------------------------------------
class PygameView:
    def __init__(self):
        events.registerListener( self )

        pygame.init()
        self.window = pygame.display.set_mode( (800,740) )
        pygame.display.set_caption( 'TITLE HERE' )

        self.background = pygame.Surface( self.window.get_size() )
        self.background.fill(black)

        self.window.blit( self.background, (0,0) )
        pygame.display.flip()

        self.opponentDisplayPositions = [ (0,5), (100,0), (200,5) ]

        self.showRobberCursor = False

        self.showHud()


    #----------------------------------------------------------------------
    def refresh(self):
        self.opponentDisplayPositions = [ (0,5), (100,0), (200,5) ]

    #----------------------------------------------------------------------
    def showHud(self):
        sbutton = SoldierButton()
        sbutton.topleft = 600, 100

        sbutton = YearOfPlentyButton()
        sbutton.topleft = 660, 100

        mbutton = MonopolyButton()
        mbutton.topleft = 720, 100

        vbutton = BuyVictoryCardButton()
        vbutton.topleft = 600, 160

        sbutton = BuySettlementButton()
        sbutton.topleft = 600, 220
        rbutton = BuyRoadButton()
        rbutton.topleft = 660, 220
        cbutton = BuyCityButton()
        cbutton.topleft = 720, 220

        dbutton = DiceButton()
        dbutton.topleft = 600, 300
        ebutton = EndTurnButton()
        ebutton.topleft = 600, 440

        tbutton = TradeButton()
        tbutton.topleft = 600, 520
        
        sbutton = SaveGameButton()
        sbutton.topleft = 600, 600

        console = Console()
        console.topleft = 10, 640

    #----------------------------------------------------------------------
    def showMap(self, board):
        # clear the screen first
        self.background.fill(black)
        self.window.blit( self.background, (0,0) )
        pygame.display.flip()

        center = self.window.get_rect().center

        row = 0
        column = 0
        tiles = board.tiles[:] # copy
        while tiles:
            t = tiles.pop(0)
            tSprite = Tile(t)
            x = 300 + tSprite.tile.graphicalPosition[0]*75
            # minus because pygame uses less = up in the y dimension
            y = 300 - tSprite.tile.graphicalPosition[1]*55
            tSprite.rect.move_ip(x,y)
        for c in catan.mapmodel.allCorners:
            corner = Corner(c)
        for e in catan.mapmodel.allEdges:
            eSprite = Edge(e)
            
    #----------------------------------------------------------------------
    def drawCursor(self):
        if not self.showRobberCursor:
            return []
        pos = pygame.mouse.get_pos()
        textImg = font_render('X', color=white, size=36)
        self.window.blit( textImg, vect_diff(pos, (-2,-2)) )
        textImg = font_render('X', color=black, size=36)
        self.window.blit( textImg, pos )
        return [textImg.get_rect().move(pos)]

    #----------------------------------------------------------------------
    def draw(self):
        self.window.blit( self.background, (0,0) )

        for tSprite in tileGroup:
            tSprite.update()
        dirtyRects = tileGroup.draw( self.window )

        for cSprite in cornerGroup:
            cSprite.update()
        dirtyRects = cornerGroup.draw( self.window )

        for eSprite in edgeGroup:
            eSprite.update()
        dirtyRects = edgeGroup.draw( self.window )

        for hudSprite in hudGroup:
            #print 'calling update on ', hudSprite
            hudSprite.update()
        dirtyRects = hudGroup.draw( self.window )

        dirtyRects += self.drawCursor()

        pygame.display.flip()
        time.sleep(1)

    #----------------------------------------------------------------------
    def onShowRobberCursor(self, player):
        self.showRobberCursor = True
        for tSprite in tileGroup:
            tSprite.hintlighted = True

    #----------------------------------------------------------------------
    def onTileClicked(self, tile):
        if self.showRobberCursor:
            events.post('RobberPlaceRequest', humanPlayer, tile)

    #----------------------------------------------------------------------
    def onRobberPlaced(self, *args):
        self.showRobberCursor = False

    #----------------------------------------------------------------------
    def onShowChooseVictim(self, player, opponents):
        cdisplay = ChooseVictimDisplay(player, opponents)
        cdisplay.center = self.window.get_rect().center

    #----------------------------------------------------------------------
    def onShowDiscard(self, player):
        ddisplay = DiscardDisplay(player)
        ddisplay.center = self.window.get_rect().center

    #----------------------------------------------------------------------
    def onShowTrade(self):
        tdisplay = TradeDisplay()
        tdisplay.center = self.window.get_rect().center

    #----------------------------------------------------------------------
    def onShowPlayerChooseTwoCards(self, player):
        if player != humanPlayer:
            return
        cdisplay = ChooseTwoCardsDisplay(player)
        cdisplay.center = self.window.get_rect().center

    #----------------------------------------------------------------------
    def onShowMonopoly(self, player):
        if player != humanPlayer:
            return
        mdisplay = MonopolyDisplay(player)
        mdisplay.center = self.window.get_rect().center


    #----------------------------------------------------------------------
    def onBoardCreated(self, board):
        self.showMap(board)

    #----------------------------------------------------------------------
    def onRefreshState(self):
        self.refresh()
        self.showMap(catan.game.board)
        for player in catan.game.players:
            playerDisplay = PlayerDisplay(player)
            if isinstance(player, catan.HumanPlayer):
                playerDisplay.topleft = 350, 660
            else:
                # CPU Player
                pos = self.opponentDisplayPositions.pop(0)
                playerDisplay.topleft = pos

    #----------------------------------------------------------------------
    def onPlayerJoin(self, player):
        playerDisplay = PlayerDisplay(player)
        if isinstance(player, catan.HumanPlayer):
            playerDisplay.topleft = 350, 660
        else:
            # CPU Player
            pos = self.opponentDisplayPositions.pop(0)
            playerDisplay.topleft = pos

    #----------------------------------------------------------------------
    def onTick(self):
        self.draw()

#------------------------------------------------------------------------------
class BoardDisplay(object):
    def __init__(self, board):
        self.board = board
        self.tiles = []
        for t in self.board.tiles:
            tSprite = Tile(t)
            self.tiles.append(tSprite)

    def align_to_center(self, centerPos):
        visitedCorners = []
        visitedEdges = []
        cornSprites = []
        remainingTiles = mapmodel.allTiles

        tSprite1 = self.tiles[0]
        tile = tSprite1.tile
        tSprite1.center = center
        tSprite.calcCornerPositions()
        remainingTiles.remove(tile)

        cornPosIdx = 0

        def visitFn(corner, edge):
            cornPosIdx += 1
            if edge and set.issubset(edge.corners, visitedCorners):
                return

            cSprite = Corner(corner)
            cSprite.center = tSprite1.cornerPositions[cornPosIdx]
            cornSprites.append(cSprite)
            visitedCorners.append(corner)

            if edge:
                otherTiles = (edge.tiles - [tile])
                if otherTiles:
                    otherTile = otherTiles[0]
                    if otherTile in remainingTiles:
                        otherTileS.setCenterFromEdge(edge, tSprite)

        walk_corners_along_tile(tile, visitFn)

#------------------------------------------------------------------------------
class CardAddButton(EasySprite):
    def __init__(self, parent, pos, cardClass, symbol='+'):
        EasySprite.__init__(self)
        self.image = font_render(symbol, size=50)
        self.rect = self.image.get_rect()
        self.rect.topleft = pos

        self.cardClass = cardClass
        self.parent = parent

    def cardSubset(self):
        return set([card for card in humanPlayer.cards
                    if isinstance(card, self.cardClass)])

#------------------------------------------------------------------------------
class CardRemoveButton(CardAddButton):
    def __init__(self, parent, pos, cardClass):
        CardAddButton.__init__(self, parent, pos, cardClass, symbol='-')

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
class DiscardTextButton(TextButton):
    def __init__(self, pos):
        EasySprite.__init__(self)
        Highlightable.__init__(self)
        events.registerListener(self)
        self.text = 'DISCARD'
        self.rect = Rect(pos[0], pos[1], 70,15)
        self.image = EasySurface(self.rect.size)
        self.draw()

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

        hudGroup.add(self)
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
            hudGroup.remove(self)
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
                events.post('DiscardRequest', self.player, self._discards)

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
class ChooseTextButton(TextButton):
    def __init__(self, pos):
        EasySprite.__init__(self)
        Highlightable.__init__(self)
        events.registerListener(self)
        self.text = 'CHOOSE'
        self.rect = Rect(pos[0], pos[1], 70,15)
        self.image = EasySurface(self.rect.size)
        self.draw()

#------------------------------------------------------------------------------
class ChooseTwoCardsDisplay(EasySprite):
    def __init__(self, player):
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

        hudGroup.add(self)
        self.dirty = True

    #----------------------------------------------------------------------
    def addChoose(self, cardClass):
        if len(self._chosen) < 2:
            self._chosen.append(cardClass)
            self.dirty = True

    #----------------------------------------------------------------------
    def removeChoose(self, cardClass):
        if self._chosen:
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
            hudGroup.remove(self)
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


#------------------------------------------------------------------------------
class MonopolyAddButton(CardAddButton):
    def click(self):
        self.parent.addMonopoly(self.cardClass)

#------------------------------------------------------------------------------
class MonopolyTextButton(TextButton):
    def __init__(self, pos):
        EasySprite.__init__(self)
        Highlightable.__init__(self)
        events.registerListener(self)
        self.text = 'MONOPOLIZE'
        self.rect = Rect(pos[0], pos[1], 80,15)
        self.image = EasySurface(self.rect.size)
        self.draw()

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

        hudGroup.add(self)
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
            hudGroup.remove(self)
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
            
            
#------------------------------------------------------------------------------
class QuitTradeButton(TextButton):
    def __init__(self, pos):
        EasySprite.__init__(self)
        Highlightable.__init__(self)
        events.registerListener(self)
        self.text = 'QUIT TRADE'
        self.rect = Rect(pos[0], pos[1], 100,12)
        self.image = EasySurface(self.rect.size)
        self.draw()

    def click(self):
        events.post('HideTrade')

#------------------------------------------------------------------------------
class ProposalMatchButton(TextButton):
    def __init__(self, parent, pos):
        EasySprite.__init__(self)
        Highlightable.__init__(self)
        events.registerListener(self)
        self.parent = parent
        self.opponent = None
        self.hidden = True
        self.text = 'Match'
        self.rect = Rect(pos[0], pos[1], 60,12)
        self.image = EasySurface(self.rect.size)
        self.draw()

    def click(self):
        if self.hidden:
            return
        if not (self.opponent and self.opponent.proposal):
            return
        self.parent.matchProposal(self.opponent.proposal)

#------------------------------------------------------------------------------
class ProposeConfirmButton(TextButton):
    def __init__(self, pos):
        EasySprite.__init__(self)
        Highlightable.__init__(self)
        events.registerListener(self)
        self.opponent = None
        self.proposal = None
        self.hidden = True
        self.text = 'Confirm'
        self.rect = Rect(pos[0], pos[1], 60,12)
        self.image = EasySurface(self.rect.size)
        self.draw()

    def click(self):
        if self.hidden:
            return
        if not (self.opponent and self.proposal):
            return
        events.post('ConfirmProposalRequest', self.opponent, self.proposal)

#------------------------------------------------------------------------------
class TradeGiveButton(CardAddButton):
    def __init__(self, parent, pos, cardClass):
        CardAddButton.__init__(self, parent, pos, cardClass, symbol='^')

    def click(self):
        group = self.cardSubset()
        given = self.parent._cardsToGive.get(self.cardClass, [])
        ungiven = group.difference(set(given))
        if ungiven:
            self.parent.addCard(ungiven.pop())

#------------------------------------------------------------------------------
class TradeTakeButton(CardAddButton):
    def __init__(self, parent, pos, cardClass):
        CardAddButton.__init__(self, parent, pos, cardClass, symbol='v')

    def click(self):
        self.parent.takeCard(self.cardClass)

#------------------------------------------------------------------------------
class TradeDisplay(EasySprite):
    def __init__(self):
        EasySprite.__init__(self)
        events.registerListener(self)
        hudGroup.add(self)
        self.image = EasySurface( (280,180) )
        self.rect = self.image.get_rect()

        # TODO: i'm not really liking these collections living here. I should
        # probably just switch to inspecting humanPlayer.proposal
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
        events.post('ProposeTrade', humanPlayer,
                    cardClassesToGive, self._cardClassesToTake)

    #----------------------------------------------------------------------
    def matchesProposal(self, proposal):
        opponentGive, opponentTake = proposal
        opponentGive = opponentGive[:] #copy
        opponentTake = opponentTake[:] #copy
        try:
            for cardClass in self._cardsToGive:
                for card in self._cardsToGive[cardClass]:
                    opponentTake.remove(cardClass)
            for cardClass, howMany in self._cardClassesToTake.items():
                for i in range(howMany):
                    opponentGive.remove(cardClass)
        except ValueError:
            return False
        if opponentGive != [] or opponentTake != []:
            return False
        return True

    #----------------------------------------------------------------------
    def addCard(self, card):
        cardClass = card.__class__
        if self._cardClassesToTake.get(cardClass):
            self._cardClassesToTake[cardClass] -= 1
        else:
            cardList = self._cardsToGive.setdefault(cardClass, [])
            cardList.append(card)
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
            group = [card for card in humanPlayer.cards
                     if isinstance(card, cls)
                     and card not in givenCards]

            draw_cards(group, self.image, x, y, 2, 3, number=True)
            x += 30

    #----------------------------------------------------------------------
    def drawOpponents(self):
        opponents = catan.game.players[:]
        opponents.remove(humanPlayer)
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
    def update(self):
        self.drawBg()
        self.drawCards()
        self.drawOpponents()
        self.drawButtons()

        self.dirty = False

    #----------------------------------------------------------------------
    def matchProposal(self, proposal):
        toGive, toTake = proposal
        newCardsToGive = {}
        newCardClassesToTake = defaultdict(lambda:0)
        # TODO: asDict returns a dict of class=>list items because doing
        # dict(group_cards(...)) makes all the items empty for some reason
        cardDict = group_cards(humanPlayer.cards, asDict=True)
        try:
            for cls in toTake:
                matchingCards = cardDict[cls]
                card = matchingCards.pop()
                cardList = newCardsToGive.setdefault(cls, [])
                cardList.append(card)
        except (StopIteration, KeyError):
            print 'there werent enough cards of that class'
            return # there weren't enough cards of that class
        for cls in toGive:
            newCardClassesToTake[cls] += 1
        self._cardsToGive = newCardsToGive
        self._cardClassesToTake = newCardClassesToTake
        self.propose()
        self.dirty = True

    #----------------------------------------------------------------------
    def onProposeTrade(self, player, toGive, toTake):
        if player == humanPlayer:
            return
        self.dirty = True

    #----------------------------------------------------------------------
    def onConfirmProposal(self, *args):
        self.reset()

    #----------------------------------------------------------------------
    def onHideTrade(self):
        hudGroup.remove(self)
        events.unregisterListener(self)
        self.giveButtons = None
        self.takeButtons = None
        self.kill()

    #----------------------------------------------------------------------
    def onMouseMotion(self, pos, buttons):
        if not self.rect.collidepoint(pos):
            return
        innerPos = vect_diff(pos, self.topleft)
        for button in (self.giveButtons.values()
                      + self.takeButtons.values()
                      + self.textButtons
                      + self.confirmButtons
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
                      + self.matchButtons):
            if button.rect.collidepoint(innerPos):
                button.click()


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
    def __init__(self, player, opponents):
        EasySprite.__init__(self)
        events.registerListener(self)
        self.image = EasySurface( (280,180) )
        self.rect = self.image.get_rect()

        self.player = player
        self.opponents = opponents

        self.oButtons = {}

        self.drawBg()
        self.drawButtons()

        hudGroup.add(self)
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
            hudGroup.remove(self)
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

#------------------------------------------------------------------------------
class PlayerDisplay(EasySprite):
    def __init__(self, player):
        EasySprite.__init__(self)
        events.registerListener(self)
        self.image = EasySurface( (80,80) )
        self.rect = self.image.get_rect()

        self.player = player
        self.active = False

        self.drawBg()

        hudGroup.add(self)
        self.dirty = True

    #----------------------------------------------------------------------
    def drawBg(self):
        self.image.fill( (0,0,20) )
        r = self.rect.move(0,0)
        r.topleft = 0,0
        pygame.draw.rect(self.image, blue, r, 8)
        
        if self.player.points >= 10:
            r2 = r.inflate(10,10)
            r2.center = r.center
            pygame.draw.rect(self.image, white, r2)

        if catan.game.state.activePlayer == self.player:
            self.active = True
        else:
            self.active = False

        if self.active:
            pygame.draw.rect(self.image, (200,200,255), r, 1)

        txtImg = font_render(str(self.player.identifier),
                             color=self.player.color)
        pos = vect_add(r.midtop, (10,4))
        self.image.blit(txtImg, pos)

        txtImg = font_render(str(self.player.points),
                             color=self.player.color)
        pos = vect_add(r.midtop, (20,4))
        self.image.blit(txtImg, pos)

    #----------------------------------------------------------------------
    def drawCards(self):
        cards = self.player.cards
        draw_cards(cards, self.image, 2, 6, 3, 3)

    #----------------------------------------------------------------------
    def drawVictoryCards(self):
        for i, card in enumerate(self.player.victoryCards):
            cardImg = drawVictoryCard(card)
            cardPos = vect_add((32,6), (3*i,3*i))
            self.image.blit(cardImg, cardPos)

        for i, card in enumerate(self.player.playedVictoryCards):
            cardImg = drawVictoryCard(card)
            cardPos = vect_add((5,50), (3*i,0))
            self.image.blit(cardImg, cardPos)


    #----------------------------------------------------------------------
    def update(self):
        if not self.dirty:
            return
        self.drawBg()
        self.drawCards()
        self.drawVictoryCards()
        self.dirty = False

    #----------------------------------------------------------------------
    def onStageChange(self, newStage):
        if newStage in [catan.Stages.preRoll,
                        catan.Stages.playerTurn]:
            self.dirty = True

        if self.player != humanPlayer:
            return

        if newStage == catan.Stages.sevenRolledDiscard:
            if len(self.player.cards) > 7:
                events.post('ShowDiscard', self.player)

        if self.player != catan.game.state.activePlayer:
            return

        elif newStage in [catan.Stages.preRollChooseVictim,
                          catan.Stages.postRollChooseVictim]:
            possibleVictims = self.player.findPossibleVictims()
            if possibleVictims:
                if len(possibleVictims) == 1:
                    events.post('RobRequest', self.player,
                                possibleVictims[0])
                else:
                    events.post('ShowChooseVictim', self.player,
                                possibleVictims)
            else:
                events.post('SkipRobRequest', self.player)


    #----------------------------------------------------------------------
    def onPlayerDrewVictoryCard(self, player, card):
        if player == self.player:
            self.dirty = True

    #----------------------------------------------------------------------
    def onDiscard(self, player):
        if player == self.player:
            self.dirty = True

    #----------------------------------------------------------------------
    def onPlayerPlacing(self, player, item):
        self.dirty = True
        if self.player == player and isinstance(item, catan.Robber):
            events.post('ShowRobberCursor', self.player)

    #----------------------------------------------------------------------
    def onRefreshState(self):
        self.dirty = True

    #----------------------------------------------------------------------
    def onConfirmProposal(self, *args):
        self.dirty = True

    #----------------------------------------------------------------------
    def onItemPlaced(self, *args):
        self.dirty = True

    #----------------------------------------------------------------------
    def onChooseTwoCards(self, player, cards):
        self.dirty = True

    #----------------------------------------------------------------------
    def onMonopoly(self, player, cards):
        self.dirty = True



humanPlayer = None

#------------------------------------------------------------------------------
def main():
    global humanPlayer
    spinner = CPUSpinnerController()
    kbController = KeyboardController()
    pygameView = PygameView()
    catan.init()
    events.post('PlayerJoin', catan.CPUPlayer(1))
    events.post('PlayerJoin', catan.CPUPlayer(2))
    events.post('PlayerJoin', catan.CPUPlayer(3))
    humanPlayer = catan.HumanPlayer(4)
    events.post('PlayerJoin', humanPlayer)
    spinner.run()

#------------------------------------------------------------------------------
_oldExceptHook = sys.excepthook
def customExceptHook(etype, evalue, etb):
    print '='*60
    print 'EXCEPTION HOOK'
    _oldExceptHook(etype, evalue, etb)
    import pdb
    retval = pdb.pm()
    print 'retval :', retval
    

if __name__ == "__main__":
    sys.excepthook = customExceptHook
    main()
