#! /usr/bin/env python

import sys
import time
import string

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
class EasySurface(pygame.Surface):
    def __init__(self, sizeSpec):
        if isinstance(sizeSpec, pygame.Rect):
            sizeSpec = sizeSpec.size
        pygame.Surface.__init__(self, sizeSpec, flags=pygame.SRCALPHA)

# -----------------------------------------------------------------------------
class EasySprite(pygame.sprite.Sprite):
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



def vect_add(v1, v2):
    return v1[0]+v2[0], v1[1]+v2[1]
    
def vect_diff(v1, v2):
    return v1[0]-v2[0], v1[1]-v2[1]

def vect_mult(v1, v2):
    return v1[0]*v2[0], v1[1]*v2[1]

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
class EndTurnButton(EasySprite):
    def __init__(self):
        EasySprite.__init__(self)
        events.registerListener(self)
        self.image = EasySurface( (150,50) )
        self.rect = self.image.get_rect()
        r = self.rect.move(0,0)
        pygame.draw.rect(self.image, blue, r, 2)

        txtImg = font_render('END TURN')
        blit_at_center(self.image, txtImg)

        hudGroup.add(self)

        self.dirty = True

    #----------------------------------------------------------------------
    def onMouseLeftDown(self, pos):
        if self.rect.collidepoint(pos):
            events.post('TurnFinishRequest', humanPlayer)


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
        self.image.fill( (0,0,0) )
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
class DiceButton(EasySprite):
    def __init__(self):
        EasySprite.__init__(self)
        self.image = EasySurface( (150,100) )
        self.rect = self.image.get_rect()

        self.rollText = dict(text='ROLL', color=(255,0,0) )
        self.diceText = dict(text='*', size=30, color=(255,0,0) )

        self.drawBg()
        self.drawText()

        hudGroup.add(self)

        events.registerListener(self)
        self.dirty = True

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
        r.topleft = 0,35
        txtImg = font_render(**self.rollText)
        blit_at_center(self.image, txtImg, rect1=r)

        r.size = 50,50
        r.topleft = 12,12
        txtImg = font_render(**self.diceText)
        self.image.blit(txtImg, r)

    #----------------------------------------------------------------------
    def update(self):
        self.image.fill( (0,0,0) )
        self.drawBg()
        self.drawText()

    #----------------------------------------------------------------------
    def onDiceRoll(self, rollValue):
        self.diceText['text'] = str(rollValue)

    #----------------------------------------------------------------------
    def onMouseLeftDown(self, pos):
        if self.rect.collidepoint(pos):
            events.post('DiceRollRequest', humanPlayer)

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
class Tile(EasySprite):
    def __init__(self, tile):
        EasySprite.__init__(self)
        events.registerListener(self)
        self.image = EasySurface( (100,100) )
        self.rect = self.image.get_rect()
        self.dirty = True
        r = self.rect

        #self.image.fill( (0,255,128) )
        text = tile.name
        textImg = font_render(text)
        self.image.blit( textImg, r.center )

        self.tile = tile
        self.calcCornerPositions()

        tileGroup.add(self)
        tileModelToSprite[tile] = self

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

        # draw the tile name
        text = self.tile.name
        textImg = font_render(text, color=(0,0,0))
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

    def onRobberPlaced(self, *args):
        self.dirty = True

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
                

#------------------------------------------------------------------------------
class Corner(EasySprite):
    def __init__(self, corner):
        #print 'making corner', corner.name
        EasySprite.__init__(self)
        self.image = EasySurface( (22,22) )
        self.rect = self.image.get_rect()
        self.corner = corner

        self.hintlighted = False
        self.highlighted = False

        self.drawBg()

        cornerGroup.add(self)
        cornerModelToSprite[corner] = self

        events.registerListener(self)
        self.dirty = True

    def drawBg(self):
        if self.highlighted:
            bgcolor = (0,255,28, 250)
        elif self.hintlighted:
            bgcolor = (0,255,28, 200)
        else:
            bgcolor = (0,255,28, 128)
        self.image.fill( bgcolor )
        text = self.corner.name
        textImg = font_render(text, size=15, color=(5,0,0))
        self.image.blit( textImg, (0,0) )

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
        if self.highlighted:
            self.highlighted = False
            self.dirty = True
        if self.hintlighted:
            self.hintlighted = False
            self.dirty = True
        if item.location == self.corner:
            self.dirty = True

    def onRobberPlaced(self, *args):
        self.dirty = True

    def onPlayerPlacing(self, player, item):
        if isinstance(player, catan.HumanPlayer):
            if self.corner in player.findFreeCornersForSettlement():
                self.hintlighted = True
                self.dirty = True

    def onMouseMotion(self, pos, buttons):
        if self.hintlighted:
            if self.rect.collidepoint(pos):
                self.highlighted = True
                self.dirty = True
            else:
                self.highlighted = False
                self.dirty = True
        
    def onMouseLeftDown(self, pos):
        if self.highlighted:
            if self.rect.collidepoint(pos):
                events.post('ClickCorner', self.corner)
                
#------------------------------------------------------------------------------
class Edge(EasySprite):
    def __init__(self, edge):
        #print 'making edge', edge.name
        EasySprite.__init__(self)
        events.registerListener(self)

        self.edge = edge

        edgeGroup.add(self)
        edgeModelToSprite[edge] = self

        if len(self.edge.corners) != 2:
            print '??'
            return

        self.hintlighted = False
        self.highlighted = False

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

        self.dirty = True

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

        if self.highlighted:
            color = (100,100,255, 255)
        elif self.hintlighted:
            color = (0,0,255, 255)
        else:
            color = (0,0,200, 255)

        #print 'drawing edge from, to', c1Sprite.center, c2Sprite.center
        pygame.draw.aaline(self.image, color,
                           vect_diff(c1Sprite.center, self.rect.topleft),
                           vect_diff(c2Sprite.center, self.rect.topleft))

        if self.edge.stuff:
            item = self.edge.stuff[0]
            txtImg = RoadSprite(item).image
            self.image.blit( txtImg, vect_diff(self.rect.center, self.rect.topleft))

        self.dirty = False

    def onItemPlaced(self, item):
        if self.hintlighted or self.highlighted:
            self.hintlighted = False
            self.highlighted = False
            self.dirty = True
        if item.location == self.edge:
            self.dirty = True

    def onHintLightEdges(self, edges):
        if self.edge in edges:
            self.hintlighted = True
            self.dirty = True

    def onRobberPlaced(self, *args):
        self.dirty = True

    def onMouseMotion(self, pos, buttons):
        if self.hintlighted:
            if self.rect.collidepoint(pos):
                self.highlighted = True
                self.dirty = True
            else:
                self.highlighted = False
                self.dirty = True
        
    def onMouseLeftDown(self, pos):
        if self.highlighted:
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
        self.background.fill( (0,0,0) )

        self.window.blit( self.background, (0,0) )
        pygame.display.flip()

        self.opponentDisplayPositions = [ (0,5), (100,0), (200,5) ]

        self.showHud()


    #----------------------------------------------------------------------
    def showHud(self):
        dbutton = DiceButton()
        dbutton.topleft = 600, 300
        ebutton = EndTurnButton()
        ebutton.topleft = 600, 440

        console = Console()
        console.topleft = 10, 640

    #----------------------------------------------------------------------
    def showMap(self, board):
        # clear the screen first
        self.background.fill( (0,0,0) )
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
            hudSprite.update()
        dirtyRects = hudGroup.draw( self.window )


        pygame.display.flip()
        time.sleep(1)

    #----------------------------------------------------------------------
    def onBoardCreated(self, board):
        self.showMap(board)

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
class PlayerDisplay(EasySprite):
    def __init__(self, player):
        EasySprite.__init__(self)
        events.registerListener(self)
        self.image = EasySurface( (80,80) )
        self.rect = self.image.get_rect()

        self.player = player
        self.active = False

        self.drawBg()

        events.registerListener(self)

        hudGroup.add(self)
        self.dirty = True

    #----------------------------------------------------------------------
    def drawBg(self):
        self.image.fill( (0,0,20) )
        r = self.rect.move(0,0)
        r.topleft = 0,0
        pygame.draw.rect(self.image, blue, r, 8)
        if self.active:
            pygame.draw.rect(self.image, (200,200,255), r, 1)

        txtImg = font_render(str(self.player.identifier), color=(0,0,0))
        self.image.blit(txtImg, r.midtop)

    #----------------------------------------------------------------------
    def drawCards(self):
        r = self.rect.move(0,0)
        r.topleft = 0,0

        cards = self.player.cards
        for i, card in enumerate(cards):
            cardImg = pygame.Surface( (10,16) )
            cardImg.fill( card_colors[card.__class__] )
            pygame.draw.rect(cardImg, white, cardImg.get_rect(), 1)
            cardPos = vect_add((2,2), (3*i,3*i))
            self.image.blit(cardImg, cardPos)

    #----------------------------------------------------------------------
    def update(self):
        self.drawBg()
        self.drawCards()

    #----------------------------------------------------------------------
    def onStageChange(self, newStage):
        if newStage == catan.Stages.preRollSoldier:
            if catan.game.state.activePlayer == self.player:
                self.active = True
                self.dirty = True
            else:
                self.active = False
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
