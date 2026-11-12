# [BTDR:FILE.EXECUTE] Execute DAT: re-resolve the scene when the component is created or the project starts
def onCreate():
    run("args[0].Refresh() if (args[0].valid and hasattr(args[0], 'Refresh')) else None", parent(), delayFrames=2)
    return

def onStart():
    run("args[0].Refresh() if (args[0].valid and hasattr(args[0], 'Refresh')) else None", parent(), delayFrames=2)
    return
