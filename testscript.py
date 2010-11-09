from twisted.spread import pb
from twisted.internet import reactor
from twisted import cred
factory = pb.PBClientFactory()

import events

myglobals = '''\
caught_args
caught_kwargs
d
remote
gameID'''
for g in myglobals.split():
    if g not in globals():
        globals()[g] = None

def catch(*args, **kwargs):
    print 'catch caught', args, kwargs
    global caught_args, caught_kwargs
    caught_args = args
    caught_kwargs = kwargs

def catch_remote(*args, **kwargs):
    global remote
    remote = args[0]

def conn():
    global d
    connection = reactor.connectTCP('localhost', 8000, factory)
    usercred = cred.credentials.UsernamePassword('user1', 'pass1')

    d.addCallback(catch_remote)
    d = factory.login(usercred)

def catch_initialSync(gameIDGameDict):
    print 'got', gameIDGameDict
    gameid, gamedict = gameIDGameDict
    global gameID
    gameID = gameid

def initialSync():
    print 'initsync'
    global d
    d.addCallback(catch_initialSync)
    d.addErrback(catch)
    d = remote.callRemote('GetGameSync')

