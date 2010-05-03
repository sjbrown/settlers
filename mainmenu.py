#! /usr/bin/env python

import sys

import catan
import events
import mapmodel
import pygameview

def run_saved_game():
    import saved_game
    saved_game.load()
    spinner = pygameview.CPUSpinnerController()
    kbController = pygameview.KeyboardController()
    pygameView = pygameview.PygameView()
    pygameview.humanPlayer = catan.game.players[-1]
    events.post('RefreshState')
    spinner.run()

#------------------------------------------------------------------------------
def main():
    import pygameview

    if len(sys.argv) > 1 and sys.argv[1] == 'load':
        mode = 'load'
    else:
        prompt = 'Load Game ("load") or Start new game (press Enter) > '
        inpoot = raw_input(prompt)
        if inpoot.lower() == 'load':
            mode = 'load'

    if mode == 'load':
        return run_saved_game()
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
