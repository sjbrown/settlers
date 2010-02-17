#! /usr/bin/env python

import catan
import mapmodel
from pprint import pformat
import network # Importing will mix-in the classes

NAME = 'save%03d' % 3

def sanityCheck():
    assert len(mapmodel.allCorners) == len(mapmodel.cornersToTiles)
    assert len(mapmodel.allCorners) == 54
    assert len(mapmodel.allEdges) == len(mapmodel.edgesToTiles)
    assert len(mapmodel.allEdges) == 72
    accum = []
    [accum.__iadd__(list(x)) for x in mapmodel.cornersToTiles.values()]
    assert len(set(accum)) == len(mapmodel.allTiles)

    t0 = catan.game.board.tiles[0]
    assert t0.terrain
    assert t0.pip or isinstance(t0.terrain, catan.Desert)

    robber = catan.game.board.robber
    assert robber

# -----------------------------------------------------------------------------
def save(fname='./'+NAME+'.py'):
    reg = {}
    dicts = {}

    def saveObj(obj):
        return obj.getStateToCopy(reg)

    dicts['game'] = saveObj(catan.game)
    dicts['gameID'] = {0: id(catan.game)}
    dicts[id(catan.game)] = dicts['game']
    dicts['state'] = saveObj(catan.game.state)
    dicts[id(catan.game.state)] = dicts['state']
    dicts['board'] = saveObj(catan.game.board)
    dicts[id(catan.game.board)] = dicts['board']
    dicts[id(catan.game.board.robber)] = saveObj(catan.game.board.robber)
    itemCounter = 0
    for p in catan.game.players:
        dicts[id(p)] = saveObj(p)
        for item in p.items:
            dicts[id(item)] = saveObj(item)
        for card in p.cards:
            dicts[id(card)] = saveObj(card)

    for t in mapmodel.allTiles:
        dicts[id(t.terrain)] = saveObj(t.terrain)
        if t.pip:
            dicts[id(t.pip)] = saveObj(t.pip)

    sanityCheck()

    flatReg = {}
    for key, val in reg.items():
        flatReg[key] = (val.__module__, val.__class__.__name__)
    content = ( 'reg=' + pformat(flatReg)
              + '\n\n'
              + 'dicts=' + pformat(dicts)
               )

    fp = file(fname, 'w')
    fp.write(content)
    fp.close()

# -----------------------------------------------------------------------------
class Placeholder(object):
    def __init__(self, objID, reg):
        if objID in reg:
            raise Exception('Making a placeholder for an obj that has'
                            ' already been retrieved (%s)' % objID)
        self.placeholder_id = objID
        reg[objID] = self
    def placeholder_setDict(self, myDict):
        self.placeholder_dict = myDict
    def placeholder_setClass(self, cls, reg):
        self.__class__ = cls
        neededObjIDs = self.setCopyableState(self.placeholder_dict, reg)
        # just ignore the neededObjIDs as the load() function will fill
        # everything in.... hopefully

network.Placeholder = Placeholder
        
# -----------------------------------------------------------------------------
def deserialize(loadReg, srcReg, dicts, objID, clsModule, clsName):
    import mapmodel
    if clsModule == 'mapmodel':
        cls = getattr(mapmodel, clsName)
    elif clsModule == 'catan':
        cls = getattr(catan, clsName)
    else:
        raise Exception("Fail")

    if objID in loadReg:
        obj = loadReg[objID]
        if isinstance(obj, Placeholder):
            # already have a placeholder object in here
            print 'setting class', cls, cls.__bases__
            obj.placeholder_setDict(dicts[objID])
            obj.placeholder_setClass(cls, loadReg)
        else:
            print '??? Skipping', obj
    else:
        obj = Placeholder(objID, loadReg)
        loadReg[objID] = obj
        obj.placeholder_setDict(dicts[objID])
        obj.placeholder_setClass(cls, loadReg)

# -----------------------------------------------------------------------------
def load(modname=NAME):
    loadReg = {}
    module = __import__(modname, globals())
    #print module.reg
    #print module.dicts
    srcReg = module.reg

    # Thaw out the board first because it contains the allTiles, allEdges,
    # and allCorners information
    gameDict = module.dicts['game']
    boardID = gameDict['board']
    clsModule, clsName = srcReg[boardID]
    deserialize(loadReg, srcReg, module.dicts, boardID, clsModule, clsName)

    for objID, clsTuple in srcReg.items():
        if objID in loadReg and not isinstance(loadReg[objID], Placeholder):
            continue
        clsModule, clsName = clsTuple

        deserialize(loadReg, srcReg, module.dicts, objID, clsModule, clsName)

    catan.game = loadReg[module.dicts['gameID'][0]]

    sanityCheck()
