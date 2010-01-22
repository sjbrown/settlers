#! /usr/bin/env python

from itertools import combinations

# How many "rings" are in the hextile "onion".  Doesn't count the center tile
RINGS = 2

allTiles = []
allCorners = []
cornersToTiles = {}
edgesToTiles = {}
centerTile = None


class Edge(object):
    counter = 0
    def __init__(self):
        self.tiles = []
        self.corners = []
        Edge.counter += 1
        self.name = 'e%02d' % Edge.counter

    def __str__(self):
        return '<%s>' % self.name
    def __repr__(self):
        return '<%s %s>' % (self.name, self.corners)

    def getTiles(self):
        return [t for t in self.tiles if t is not None]

    def cornerTileDistanceToCenter(self):
        '''Take the corner which is closest to the center, find its tile
        which is closest to center, and return that tile's distance to the
        center tile
        '''
        innermostCorner = min(self.corners)
        return innermostCorner.tileDistance()

    def addTile(self, tile):
        assert isinstance(tile, Tile)
        if self not in edgesToTiles:
            edgesToTiles[self] = [tile]
        else:
            edgesToTiles[self].append(tile)
        self.tiles.append(tile)
        tile.addEdge(self)
        assert len(self.tiles) <= 2

    def addCorner(self, corner):
        if corner in self.corners:
            assert False, "already in corners"

        self.corners.append(corner)
        assert len(self.corners) <= 2
        for t in self.tiles:
            if t is None:
                continue
            if corner not in t.corners:
                t.addCorner(corner)

    def finish(self):
        origCorner = self.corners[0]
        ctiles = cornersToTiles[origCorner]

        if self.cornerTileDistanceToCenter() >= RINGS:
            # this edge is on the edge of the water, so it doesn't lie
            # between two tiles.
            for t in ctiles:
                if self in t.edges:
                    assert False, 'never get here'
                if len( [e for e in origCorner.getEdges() if t in e.tiles] ) == 2:
                    continue #that tile already has 2 edges
                self.tiles.append(None)
                self.addTile(t)
                for corner in self.corners:
                    if corner not in t.corners:
                        t.addCorner(corner)
                break # only add myself to the first ctile
            return

        if len(ctiles) == 1:
            self.addTile(ctiles[0])
        else:
            for combo in combinations(ctiles, 2):
                result = findEdgeBetween(*combo)
                if not result:
                    t1, t2 = combo
                    self.tiles = [t1, t2]
                    t1.addEdge(self)
                    t2.addEdge(self)
                    return


        if len(self.tiles) == 2:
            return

        elif len(self.tiles) == 1:
            t1 = self.tiles[0]
            assert len(t1.corners) != 6

            t2 = Tile()
            self.addTile(t2)
            for t in [t1,t2]:
                for corner in self.corners:
                    if corner not in t.corners:
                        t.addCorner(corner)

        elif len(self.tiles) == 0:
            t1 = ctiles[0]
            self.addTile(t1)
            t2 = Tile()
            self.addTile(t2)
            for t in [t1,t2]:
                for corner in self.corners:
                    if corner not in t.corners:
                        t.addCorner(corner)


class Corner(object):
    def __init__(self):
        self.edges = []
        allCorners.append(self)
        self.cornerDistance = None
        self.name = 'c%02d' % (allCorners.index(self) + 1)

    def __str__(self):
        return '<%s>' % self.name
    def __repr__(self):
        return str(self)

    def __cmp__(self, other):
        return cmp(self.tileDistance(), other.tileDistance())
    def __eq__(self, other):
        return self is other
    def __ne__(self, other):
        return not self == other

    def getEdges(self):
        return [e for e in self.edges if e is not None]

    def tileDistance(self):
        ctiles = cornersToTiles[self]
        innermostTile = min(ctiles)
        return innermostTile.tileDistance

    def addTile(self, tile):
        if self not in cornersToTiles:
            cornersToTiles[self] = [tile]
        else:
            cornersToTiles[self].append(tile)

    def addEdge(self, edge):
        self.edges.append(edge)
        if edge.corners:
            if (self.cornerDistance == None
                or edge.corners[0].cornerDistance < self.cornerDistance):
                self.cornerDistance = edge.corners[0].cornerDistance + 1
        edge.addCorner(self)

    def finish(self):
        if self.cornerDistance >= RINGS*2:
            # add a None to the edges list, as distant corners only
            # have 2 edges
            self.edges.append(None)

        while len(self.edges) < 3:
            edge = Edge()
            self.addEdge(edge)
            edge.finish()
        

class Tile(object):
    def __init__(self):
        self.pip = None
        self.terrain = None
        self.corners = []
        self.edges = []
        allTiles.append(self)
        self.tileDistance = None # distance to center tile
        if len(allTiles) == 1:
            self.tileDistance = 0
        self.name = 't%02d' % (allTiles.index(self) + 1)

    def __str__(self):
        return '<%s>' % self.name
    def __repr__(self):
        return str(self)

    def __cmp__(self, other):
        if isinstance(other, Tile):
            return cmp(self.tileDistance, other.tileDistance)
        assert False, "comparing a Tile to a non-Tile"

    def __eq__(self, other):
        return self is other
    def __ne__(self, other):
        return not self == other

    def addCorner(self, corner, findSpot=False):
        assert corner not in self.corners
        self.corners.append(corner)
        corner.addTile(self)
        if findSpot:
            dangEdge = self.danglingEdge()
            if dangEdge:
                corner.addEdge(dangEdge)
            if len(self.edges) == 6:
                dangEdge = self.danglingEdge()
                corner.addEdge(dangEdge)

    def addEdge(self, edge):
        self.edges.append(edge)
        assert len(self.edges) <= 6
        self.calculateNewDistance(edge)

    def calculateNewDistance(self, edge):
        if len(edge.tiles) == 1:
            return
        for tile in edge.tiles:
            if tile != self:
                otherTile = tile
        if otherTile is None or otherTile.tileDistance == None:
            return
        newDist = otherTile.tileDistance + 1
        if self.tileDistance == None or self.tileDistance > newDist:
            self.tileDistance = newDist

    def danglingEdge(self):
        for e in self.edges:
            if len(e.corners) < 2:
                return e

    def finish(self):
        while len(self.corners) < 6:
            corner = Corner()
            self.addCorner(corner, findSpot=True)
            if self.tileDistance == 0:
                corner.cornerDistance = 0
            corner.finish()
            #pygameDisplay()

def findEdgeBetween(tile1, tile2):
    for e in tile1.edges:
       if tile2 in e.tiles:
           return e

def display(tile, indent='', finished=None):
    if finished is None:
        finished = []
    print indent, tile,
    for e in tile.edges:
        for t in e.tiles:
            if t != tile:
                print '%s-%s' % (e, t),
    finished.append(tile)
    for e in tile.edges:
        for t in e.tiles:
            if t == None:
                continue
            if t not in finished:
                #print 'gonna print *', t
                print '\n'
                display(t, indent+'   ', finished)
    print ''

def pygameDisplay():
    '''make a call to this method from the middle of the build algorithm
    to see what the map looks like at that point.
    '''
    try:
        import pygameview
        view = pygameview.PygameView()
        view.showMap()
        view.draw()
    except ImportError:
        pass

def build():
    global centerTile
    centerTile = Tile()

    while True:
        unfinishedTiles = [t for t in allTiles
                           if len(t.corners) < 6]
        if unfinishedTiles:
            unfinishedTiles[0].finish()
        else:
            break

if __name__ == '__main__':
    build()
    display(centerTile)
