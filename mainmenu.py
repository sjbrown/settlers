#! /usr/bin/env python

import sys

import catan
import events
import mapmodel
import pygameview

#------------------------------------------------------------------------------
def main():
    import pygameview

    inpoot = raw_input('Load Game ("load") or Start new game (press Enter) > ')
    if inpoot.lower() == 'load':
        import saved_game
        saved_game.load()
        spinner = pygameview.CPUSpinnerController()
        kbController = pygameview.KeyboardController()
        pygameView = pygameview.PygameView()
        pygameview.humanPlayer = catan.game.players[-1]
        events.post('RefreshState')
        spinner.run()
    else:
        return pygameview.main()

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
