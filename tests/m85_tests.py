# [BTDR:FILE.TEST.M85] m85_tests.py — 0.8.5: shadow range and probe grid fit to walls and ceilings ([BTDR:EXT.SOLIDBOXES]).
# Run: exec(open(project.folder + '/btdr/tests/m85_tests.py', encoding='utf-8').read())
# Result: btdr/out/m85_tests.txt (first line STATUS PASS / FAIL); the test network is removed.
#   an open room (floor, three 0.1-thick walls, a ceiling) with a small box: the shadow range and the probe grid cover
#   the walls and the ceiling, the floor alone is left out; an outdoor scene (big ground plane + one object) still
#   fits the object, not the ground
import traceback
import numpy as np
BT = globals().get('BTDR_SRC', project.folder + '/btdr')   # BTDR_SRC: run from another project (0.9.6)
LOG, FAILS = [], []
NAME = 'm85_test'
def check(name, ok, detail=''):
    LOG.append('%s  %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok: FAILS.append(name)
def finish():
    open(BT + '/out/m85_tests.txt', 'w', encoding='utf-8').write(
        'STATUS %s (%d checks, %d failed)\n' % ('FAIL' if FAILS else 'PASS', len(LOG), len(FAILS)) + '\n'.join(LOG))
    t = op('/project1/' + NAME)
    if t: t.destroy()
def step(fn, frames):
    def wrapped():
        try:
            fn()
        except Exception:
            LOG.append('FAIL  exception\n' + traceback.format_exc()); FAILS.append('exception'); finish()
    run("args[0]()", wrapped, delayFrames=frames)
def box(S, n, t, size):
    g = S.create(geometryCOMP, n)
    for c in list(g.children): c.destroy()
    s = g.create(boxSOP, 's'); s.render = s.display = True
    s.par.sizex, s.par.sizey, s.par.sizez = size
    g.par.tx, g.par.ty, g.par.tz = t
    return g
ST = {}
try:
    open(BT + '/out/m85_tests.txt', 'w', encoding='utf-8').write('STATUS RUNNING')
    P = op('/project1')
    if P.op(NAME): P.op(NAME).destroy()
    T = P.create(baseCOMP, NAME); T.nodeX, T.nodeY = 2400, -1400
    room = T.create(baseCOMP, 'room')
    box(room, 'floor', (0, -0.05, 0), (6, 0.1, 6))
    box(room, 'backwall', (0, 1.5, -2.0), (6, 3, 0.1))
    box(room, 'leftwall', (-2.0, 1.5, 0), (0.1, 3, 6))
    box(room, 'rightwall', (2.0, 1.5, 0), (0.1, 3, 6))
    box(room, 'ceiling', (0, 3.05, -0.6), (6, 0.1, 3.0))
    box(room, 'thing', (0.3, 0.3, -0.5), (0.6, 0.6, 0.6))
    c = room.create(cameraCOMP, 'cam1'); c.par.tz = 5
    l = room.create(lightCOMP, 'light1'); l.par.lighttype = 'distant'; l.par.rx = -55
    R = room.loadTox(BT + '/release/BTDR.tox'); R.name = 'renderBTDR1'
    R.par.Startupinfo = False; R.par.Cover = False; R.par.Resolutionw, R.par.Resolutionh = 320, 180
    ST['R'] = R
    def s1():
        R = ST['R']
        R.Refresh()
        cy, rng = R.par.Shadowcentery.eval(), R.par.Shadowrange.eval()
        check('EXT.SOLIDBOXES shadow range covers the room height', 1.2 < cy < 1.8 and rng > 8.0, 'centre y %.2f, range %.2f' % (cy, rng))
        g = R.op('rt_probe_grid')
        top = g.par.ty.eval() + g.par.sizey.eval() / 2.0
        lo_z = g.par.tz.eval() - g.par.sizez.eval() / 2.0
        check('EXT.SOLIDBOXES probe grid reaches the back wall and the ceiling',
              top > 2.9 and lo_z < -1.9, 'grid top %.2f, back %.2f' % (top, lo_z))
        cast = R.fetch('shadow_casters', [])
        check('floor still left out of the shadow pass, walls and ceiling cast', len(cast) == 5, str(cast))
        # outdoor: a big ground plane and one object -> the fit follows the object
        out = T.create(baseCOMP, 'outdoor')
        box(out, 'ground', (0, -0.05, 0), (40, 0.1, 40))
        box(out, 'statue', (0, 1, 0), (1, 2, 1))
        c2 = out.create(cameraCOMP, 'cam1'); c2.par.tz = 6
        R2 = out.loadTox(BT + '/release/BTDR.tox'); R2.name = 'renderBTDR1'
        R2.par.Startupinfo = False; R2.par.Cover = False; R2.par.Resolutionw, R2.par.Resolutionh = 320, 180
        ST['R2'] = R2
        room.destroy()
        step(s2, 30)
    def s2():
        R2 = ST['R2']
        R2.Refresh()
        rng = R2.par.Shadowrange.eval()
        check('outdoor: shadow range fits the object, not the 40 m ground', rng < 6.0, 'range %.2f' % rng)
        e = [(c.name, c.errors()[:60]) for c in R2.findChildren() if c.valid and c.errors()]
        check('no errors', not e, str(e[:3]))
        step(finish, 2)
    step(s1, 60)
except Exception:
    LOG.append('FAIL  exception\n' + traceback.format_exc()); FAILS.append('exception'); finish()
