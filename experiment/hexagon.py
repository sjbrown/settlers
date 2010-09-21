import math
from math import sin, cos, sqrt
import shutil
import os
import time

inkscape_pt_to_mm = 3.8655


def reasonable(x):
    if -0.0000001 < x < 0.0000001:
        return 0
    return x

# -----------------------------------------------------------------------------
def makedeltas(x=0, y=0, edgesize=100):
    if type(x) in (tuple, list):
        x, y = x
    yield [x,y]
    for i in range(6):
        dx = edgesize * math.cos((i/3.0)*math.pi)
        dy = edgesize * math.sin((i/3.0)*math.pi)
        dx = reasonable(dx)
        dy = reasonable(dy)
        yield [dx,dy]


svgID = 1

# -----------------------------------------------------------------------------
class Hex(object):
    edgesize = 42.5
    def __init__(self, xy=(0,0), edgesize=None):
        self.xy = xy
        if edgesize == None:
            self.edgesize = Hex.edgesize
        else:
            self.edgesize = edgesize

        self.edgecolor = '000000'
        self.fillcolor = 'ffffff'

        global svgID
        self.pathname = 'genpath' + str(svgID)
        svgID += 1

    # -------------------------------------------------------------------------
    def getWidth(self):
        r'''
               --------
              /        \
             /          \
            /            \
           /..............\
           \    width     /
            \            /
             \          /
              \        /
               --------
        '''
        return self.edgesize * 2
    width = property(getWidth)

    # -------------------------------------------------------------------------
    def getCenterToEdgeNormal(self):
        r'''
               --------
              /    |   \
             /    A|    \
            /      |     \
           /       |......\
           \          B   /
            \            /
             \          /
              \        /
               --------
        center to edge normal = A
        '''
        return self.edgesize * math.sin((1/3.0)*math.pi)
    centerToEdgeNormal = property(getCenterToEdgeNormal)
    hh = centerToEdgeNormal # "hh" = "half height"

    # -------------------------------------------------------------------------
    def getCenter(self):
        x,y = self.xy
        dx = self.edgesize/2.0
        dy = self.centerToEdgeNormal
        return (x+dx, y+dy)

    def setCenter(self, x=0, y=0):
        if type(x) in (tuple, list):
            x, y = x

        # the delta of travelling from the center to the topleft
        dx = -(self.edgesize/2.0)
        dy = -self.centerToEdgeNormal
        self.xy = (x+dx, y+dy)
    center = property(getCenter, setCenter)

    # -------------------------------------------------------------------------
    def getCenterX(self):
        return self.center[0]
    def setCenterX(self, x):
        self.center = x, self.center[1]
    centerX = property(getCenterX, setCenterX)

    # -------------------------------------------------------------------------
    def getCenterY(self):
        return self.center[1]
    def setCenterY(self, y):
        self.center = self.center[0], y
    centerY = property(getCenterY, setCenterY)

    # -------------------------------------------------------------------------
    def getDeltaGenerator(self):
        return makedeltas(*self.xy, edgesize=self.edgesize)
    deltaGen = property(getDeltaGenerator)

    # -------------------------------------------------------------------------
    def tosvg(self):
        s = ''
        for x,y in self.deltaGen:
            x *= inkscape_pt_to_mm
            y *= inkscape_pt_to_mm
            s += ' %s,%s' % (x,y)
        #style="fill:#ffffff;fill-opacity:1;
        #stroke:#000000;stroke-width:1;
        #stroke-miterlimit:4;stroke-opacity:1;stroke-dasharray:none"
        subs = dict(points=s)
        subs.update(self.__dict__)
        return '''<path
               id="%(pathname)s"
               style="fill:#%(fillcolor)s;stroke:#%(edgecolor)s;stroke-width:1"
               d="m %(points)s
               z" />
               ''' % subs
               #''' % dict(pathname=self.pathname, edgecolor=self.edgecolor,
                      #points=s)

# -----------------------------------------------------------------------------
def prin():
    for x,y in makedeltas():
        print ','.join([str(a) for a in [x,y]])

# -----------------------------------------------------------------------------
def hexgrid(rows=5,cols=5):
    for i in range(rows):
        for j in range(cols):
            h = Hex()
            yAdjust = (j%2)*h.hh
            h.center = (j*1.5*h.edgesize, 2*i*h.hh + yAdjust)
            yield h


# -----------------------------------------------------------------------------
def distance(p1, p2):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return sqrt( dx**2 + dy**2 )

# -----------------------------------------------------------------------------
def direction_vector(p1, p2, scale=1.0):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    hyp_len = distance(p1,p2)
    if hyp_len == 0:
        return [0,0]
    mult = scale / hyp_len
    return vector_scalar_mult((dx,dy), mult)

# -----------------------------------------------------------------------------
def direction_vector_and_distance(p1, p2, scale=1.0):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    hyp_len = sqrt( dx**2 + dy**2 )
    if hyp_len == 0:
        return ([0,0], 0)
    mult = scale / hyp_len
    return (vector_scalar_mult((dx,dy), mult), hyp_len)

# -----------------------------------------------------------------------------
def vector_scalar_mult(v, s):
    return (v[0]*s, v[1]*s)

# -----------------------------------------------------------------------------
def vector_add(v1, v2):
    return v1[0]+v2[0], v1[1]+v2[1]

def makeColorInHexadecimal_1(h):
    dist = distance(h.center, (600,600))
    i = int(((1+sin(dist))/2)*255)
    print i,
    numpart = hex(i).split('x')[1]
    print numpart
    return ('% 2s' % numpart).replace(' ', '0')

def makeColorInHexadecimal_2(h):
    dist = distance(h.center, (600,600))
    dist /= 2.0
    i = int(((1+sin(dist))/2)*255)
    print i,
    numpart = hex(i).split('x')[1]
    print numpart
    return ('% 2s' % numpart).replace(' ', '0')

def makeColorInHexadecimal_3(h):
    dist = distance(h.center, (350,300))
    dist /= 20.0
    between0and1 = (1+sin(dist))/2.0
    print between0and1
    i = int(between0and1*255)
    print i,
    numpart = hex(i).split('x')[1]
    print numpart
    return ('% 2s' % numpart).replace(' ', '0')

def sin_intensity(h):
    dist = distance(h.center, (350,260))
    dist /= 20.0
    between0and1 = (1+sin(dist))/2.0
    return between0and1

def makeColorInHexadecimal_4(h):
    dist = distance(h.center, (600,600))
    dist /= 200.0
    between0and1 = (1+sin(dist))/2.0
    i = int(between0and1*255)
    print i,
    numpart = hex(i).split('x')[1]
    print numpart
    return ('% 2s' % numpart).replace(' ', '0')


def draw():
    s = ''
    #h = Hex((0,0))
    #h.center = (0,0)
    #s += h.tosvg()
    #h.setCenter(0,h.hh*2)
    #s += h.tosvg()
    #h.setCenter(0,h.hh*4)
    #s += h.tosvg()
    #h2 = Hex()
    #h2.center = (0,0)
    #h2.centerX += 1.5*h2.edgesize
    #h2.centerY += h2.hh
    #s += h2.tosvg()
    Hex.edgesize=10
    #for h in hexgrid(30,50):
        #blue = makeColorInHexadecimal_3(h)
        #color = 'ffff' + blue
        #h.fillcolor = color
        #s += h.tosvg()
    for h in hexgrid(30,50):
        #s += h.tosvg()
        bzone = sin_intensity(h)
        numInternalHexes = int(bzone * 5)
        print 'numInternalHexes', numInternalHexes
        hi = Hex()
        hi.edgesize = h.edgesize - 2*(numInternalHexes)
        hi.center = h.center
        s += hi.tosvg()
        #if numInternalHexes == 0:
            #s += h.tosvg()
            #
        #for i in range(numInternalHexes):
            #hi = Hex()
            #hi.edgesize = h.edgesize - 2*(i+1)
            #hi.center = h.center
            #s += hi.tosvg()

    return s

fname = '/a/hexagons.svg'
if os.path.exists(fname):
    tstamp = str(time.time())
    bakFname = '/tmp/hexagons.svg.'+tstamp
    shutil.copy(fname, bakFname)
fp = file(fname, 'w')
fp.write('''\
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!-- Created with Inkscape (http://www.inkscape.org/) -->

<svg
   xmlns:dc="http://purl.org/dc/elements/1.1/"
   xmlns:cc="http://creativecommons.org/ns#"
   xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
   xmlns:svg="http://www.w3.org/2000/svg"
   xmlns="http://www.w3.org/2000/svg"
   xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
   xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
   width="744.09448819"
   height="1052.3622047"
   id="svg2"
   version="1.1"
   inkscape:version="0.47 r22583"
   >
  <sodipodi:namedview
     id="base"
     pagecolor="#ffffff"
     bordercolor="#666666"
     borderopacity="1.0"
     inkscape:pageopacity="0.0"
     inkscape:pageshadow="2"
     inkscape:zoom="0.70998174"
     inkscape:cx="336.79831"
     inkscape:cy="990.30753"
     inkscape:document-units="mm"
     inkscape:current-layer="layer1"
     showgrid="false"
     inkscape:window-width="1280"
     inkscape:window-height="745"
     inkscape:window-x="0"
     inkscape:window-y="36"
     inkscape:window-maximized="1" />
  <metadata
     id="metadata7">
    <rdf:RDF>
      <cc:Work
         rdf:about="">
        <dc:format>image/svg+xml</dc:format>
        <dc:type
           rdf:resource="http://purl.org/dc/dcmitype/StillImage" />
        <dc:title />
      </cc:Work>
    </rdf:RDF>
  </metadata>
  <g
     inkscape:label="Layer 1"
     inkscape:groupmode="layer"
     id="layer1">
    <path
       style="fill:#ff00ff;fill-opacity:1;stroke:#000000;stroke-width:3;stroke-miterlimit:4;stroke-opacity:1"
       d="m 200,0    -90,0 -43,-75 43,-75    87,0 43,75 -43,75 z"
       id="mainhex" />

    <!-- ======================================== -->
    ''' + draw() + '''
    <!-- ======================================== -->
  </g>

</svg>
''')
fp.close()
