#! /usr/bin/env python

import time

import pygame
import pygame.sprite

import events
import catan

tileGroup = pygame.sprite.RenderUpdates()
tileModelToSprite = {}
cornerGroup = pygame.sprite.RenderUpdates()
cornerModelToSprite = {}

#------------------------------------------------------------------------------
class CPUSpinnerController:
    def __init__(self):
        events.registerListener( self )
        self.keepGoing = 1

    def run(self):
        while self.keepGoing:
            events.post(events.Tick())

    def on_Quit(self):
        #this will stop the while loop from running
        self.keepGoing = False


#------------------------------------------------------------------------------
class Tile(pygame.sprite.Sprite):
    def __init__(self, tile):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.Surface( (100,100) )
        self.rect = self.image.get_rect()
        self.dirty = True
        r = self.rect

        #self.image.fill( (0,255,128) )
        font = pygame.font.Font(None, 20)
        text = tile.name
        textImg = font.render(text, 1, (255,0,0))
        self.image.blit( textImg, r.center )

        self.tile = tile
        self.cornerPositions = [
                                r.midright,
                                (2*r.width/3, r.top),
                                (2*r.width/3, r.bottom),
                                (r.width/3, r.top),
                                (r.width/3, r.bottom),
                                r.midleft,
                                ]

        tileGroup.add(self)
        tileModelToSprite[tile] = self

    def update(self):
        if not self.dirty:
            return

        #self.image.fill( (0,255,128) )
        font = pygame.font.Font(None, 20)
        text = self.tile.name
        textImg = font.render(text, 1, (255,0,0))
        self.image.blit(textImg, (self.rect.width/2, self.rect.height/2) )
        for i, c in enumerate(self.tile.corners):
            corner = cornerModelToSprite[c]
            corner.rect.center = self.cornerPositions[i]
            corner.rect.clamp_ip(self.image.get_rect())
            #self.image.blit(corner.image, corner.rect.topleft)
        for i, e in enumerate(self.tile.edges):
            font = pygame.font.Font(None, 15)
            text = e.name
            textImg = font.render(text, 1, (0,0,255))
            if len(e.corners) == 2:
                c1, c2 = e.corners
                corner = cornerModelToSprite[c1]
                pos1 = corner.rect.center
                corner = cornerModelToSprite[c2]
                pos2 = corner.rect.center
                pygame.draw.aaline(self.image, (0,0,255), pos1, pos2)
                r = pygame.Rect(pos1[0], pos1[1],
                                (pos2[0] - pos1[0]), (pos2[1] - pos1[1]))
                self.image.blit(textImg, r.center)
            else:
                self.image.blit(textImg, (40,14*i))
        self.dirty = False
                

#------------------------------------------------------------------------------
class Corner(pygame.sprite.Sprite):
    def __init__(self, corner):
        print 'making corner', corner.name
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.Surface( (22,22) )
        self.rect = self.image.get_rect()
        r = self.rect

        self.image.fill( (0,255,28) )
        font = pygame.font.Font(None, 15)
        text = corner.name
        textImg = font.render(text, 1, (5,0,0))
        self.image.blit( textImg, r.topleft )

        self.corner = corner
        cornerGroup.add(self)
        cornerModelToSprite[corner] = self

#------------------------------------------------------------------------------
class PygameView:
    def __init__(self):
        events.registerListener( self )

        pygame.init()
        self.window = pygame.display.set_mode( (800,840) )
        pygame.display.set_caption( 'TITLE HERE' )

        self.background = pygame.Surface( self.window.get_size() )
        self.background.fill( (0,0,0) )

        self.window.blit( self.background, (0,0) )
        pygame.display.flip()


    #----------------------------------------------------------------------
    def showMap(self):
        # clear the screen first
        self.background.fill( (0,0,0) )
        self.window.blit( self.background, (0,0) )
        pygame.display.flip()

        catan.init()
        board = catan.game.board

        row = 0
        column = 0
        for i, t in enumerate(board.tiles):
            sprite = Tile(t)
            x = 300 + sprite.tile.graphicalPosition[0]*75
            # minus because pygame uses less = up in the y dimension
            y = 300 - sprite.tile.graphicalPosition[1]*75
            sprite.rect.move_ip(x,y)
        for c in catan.mapmodel.allCorners:
            corner = Corner(c)

    #----------------------------------------------------------------------
    def draw(self):
        self.window.blit( self.background, (0,0) )

        for tile in tileGroup:
            tile.update()
            dirtyRects = tileGroup.draw( self.window )

        pygame.display.flip()
        time.sleep(1)

    #----------------------------------------------------------------------
    def on_Tick(self):
        self.draw()

#------------------------------------------------------------------------------
def main():

    spinner = CPUSpinnerController()
    pygameView = PygameView()
    pygameView.showMap()
    spinner.run()

if __name__ == "__main__":
    main()
