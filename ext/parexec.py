# [BTDR:FILE.PAREXEC] Parameter Execute DAT: custom parameters of renderBTDR -> extension
def onValueChange(par, prev):
    n = par.name
    if n in ('Camera', 'Geometry', 'Lights', 'Shadowfit', 'Transparency', 'Refr', 'Blend', 'Refrmethod'):
        parent().Refresh()
    elif n.startswith('Blend') and n[5:6].isdigit():
        # [BTDR:EXT.SLOTS] Blended slots: the geometry pattern rebuilds; mode / lit / soft are bound by expression
        if n.endswith('geo'):
            parent().Refresh()
    elif n.startswith('Refr') and n[4:5].isdigit():
        # [BTDR:EXT.SLOTS] Refractive slots: a preset fills the slot; geometry / shadow / ray-tracing changes rebuild
        i = int(''.join(c for c in n[4:] if c.isdigit()))
        if n.endswith('preset'):
            parent().ApplyPreset(i)
        elif n.endswith(('geo', 'shadow', 'inrt')):
            parent().Refresh()
        elif n.endswith(('ior', 'absorb', 'thin')) and parent().par.Refrmethod.eval() != 'screen':
            parent().Refresh()           # the traced glass reads IOR / absorption from rt_mat ([BTDR:EXT.RTREFR])
    elif n == 'Quality':
        parent().ApplyQuality()
    return

def onPulse(par):
    if par.name == 'Refresh':
        parent().Refresh()
    return
