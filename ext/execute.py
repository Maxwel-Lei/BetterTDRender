# [BTDR:FILE.EXECUTE] Execute DAT: re-resolve the scene when the component is created or the project starts.
# The cover goes up first ([BTDR:EXT.COVER]) and the author / contact dialog opens ([BTDR:EXT.INFO]).
def _start():
    cs = op('cover_state')
    if cs is not None:
        cs.par.value0 = 1
        cs.par.value1 = 0
    # [BTDR:EXT.PAUSED] refresh right away: with the timeline paused frames may not advance and a delayed call
    # would never run (0.7.4: the component stayed on its loading screen). 
    try:
        parent().Refresh()
    except Exception:
        pass
    # and again two frames later: a component that is renamed right after loading (a tox inside a tox, a paste)
    # was resolved against its old path
    run("args[0].Refresh() if (args[0].valid and hasattr(args[0], 'Refresh')) else None", parent(), delayFrames=2)
    run("args[0].ShowInfo(once=True) if (args[0].valid and hasattr(args[0], 'ShowInfo')) else None", parent(), delayFrames=5)

def onCreate():
    _start()
    return

def onStart():
    _start()
    return
