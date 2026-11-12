# [BTDR:FILE.PAREXEC] Parameter Execute DAT: custom parameters of renderBTDR -> extension
def onValueChange(par, prev):
    n = par.name
    if n in ('Camera', 'Geometry', 'Lights', 'Shadowfit'):
        parent().Refresh()
    elif n == 'Quality':
        parent().ApplyQuality()
    return

def onPulse(par):
    if par.name == 'Refresh':
        parent().Refresh()
    return
