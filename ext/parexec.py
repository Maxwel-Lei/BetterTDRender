# [BTDR:FILE.PAREXEC] Parameter Execute DAT: custom parameters of renderBTDR -> extension
def onValueChange(par, prev):
    n = par.name
    if n in ('Camera', 'Geometry', 'Lights', 'Shadowfit', 'Transparency', 'Refr'):
        parent().Refresh()
    elif n.startswith('Refr') and n[4:5].isdigit():
        # [BTDR:EXT.SLOTS] Refractive slots: a preset fills the slot; geometry / shadow / ray-tracing changes rebuild
        i = int(''.join(c for c in n[4:] if c.isdigit()))
        if n.endswith('preset'):
            parent().ApplyPreset(i)
        elif n.endswith(('geo', 'shadow', 'inrt')):
            parent().Refresh()
    elif n == 'Quality':
        parent().ApplyQuality()
    return

def onPulse(par):
    if par.name == 'Refresh':
        parent().Refresh()
    return
